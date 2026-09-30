from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = Path(__file__).resolve().parent
REPORTS_ROOT = REPO_ROOT / "performance" / "reports" / "runs"
RUN_SCRIPT = REPO_ROOT / "performance" / "run-test.ps1"
STATE_FILE = "web-state.json"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

ALLOWED_FILES = {
    "report.json",
    "report.csv",
    "report.html",
    "validation.json",
    "prometheus.json",
    "k6-summary.json",
    "controller.log",
}
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/icons.svg": ("icons.svg", "image/svg+xml"),
}

SCENARIOS: dict[str, dict[str, Any]] = {
    "product-read": {
        "label": "商品查询阶梯压测",
        "description": "验证商品查询在缓存、读副本和多实例配置下的吞吐与延迟。",
        "focus": ["RPS", "p95 / p99", "Redis 命中率", "数据库查询量"],
    },
    "seckill-contention": {
        "label": "秒杀库存争抢",
        "description": "模拟大量用户同时抢购有限库存，检查原子扣减、幂等和业务一致性。",
        "focus": ["有效订单", "超卖", "重复订单", "最终库存"],
    },
    "traffic-spike": {
        "label": "瞬时洪峰",
        "description": "在短时间内从低流量升至高峰，观察网关、连接池和服务实例的抗冲击能力。",
        "focus": ["峰值 RPS", "错误率", "超时率", "恢复状态"],
    },
    "stability-soak": {
        "label": "长时间稳定性",
        "description": "持续运行较长时间，观察内存、连接、延迟和消息积压是否持续漂移。",
        "focus": ["延迟漂移", "连接数", "Kafka 积压", "容器资源"],
    },
}
MODES = {"distributed", "baseline"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def valid_run_id(run_id: str) -> bool:
    return bool(RUN_ID_PATTERN.fullmatch(run_id))


def parse_int(payload: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return parsed


def normalize_base_url(value: Any) -> str:
    base_url = str(value or "http://frontend_nginx").strip().rstrip("/")
    if base_url not in {"http://frontend_nginx", "http://host.docker.internal"}:
        raise ValueError("base_url must target frontend_nginx or host.docker.internal")
    return base_url


def powershell_executable() -> str:
    for candidate in ("pwsh", "powershell"):
        executable = shutil.which(candidate)
        if executable:
            return executable
    return "powershell"


def tail_text(path: Path, max_lines: int = 40) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return []


def phase_from_log(line: str) -> str | None:
    normalized = line.strip().lower()
    phase_map = (
        ("starting core services", "启动核心服务"),
        ("starting prometheus", "启动监控组件"),
        ("resetting", "重置测试数据"),
        ("seeding", "准备测试数据"),
        ("running k6", "执行 k6 场景"),
        ("waiting", "等待异步状态收敛"),
        ("validating", "校验业务一致性"),
        ("collecting prometheus", "采集 Prometheus 指标"),
        ("generating", "生成测试报告"),
        ("reports:", "报告已生成"),
    )
    for marker, phase in phase_map:
        if marker in normalized:
            return phase
    return None


@dataclass
class RunTask:
    run_id: str
    request: dict[str, Any]
    status: str = "queued"
    phase: str = "等待启动"
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    ended_at: str | None = None
    exit_code: int | None = None
    error: str | None = None
    last_log: str = ""
    process: subprocess.Popen[str] | None = field(default=None, repr=False)
    stop_requested: bool = False

    @property
    def run_directory(self) -> Path:
        return REPORTS_ROOT / self.run_id

    @property
    def log_path(self) -> Path:
        return self.run_directory / "controller.log"

    def public_state(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "request": self.request,
            "status": self.status,
            "phase": self.phase,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "error": self.error,
            "last_log": self.last_log,
            "log_lines": tail_text(self.log_path),
        }


RUNS: dict[str, RunTask] = {}
RUNS_LOCK = threading.RLock()


def state_path(run_id: str) -> Path:
    return REPORTS_ROOT / run_id / STATE_FILE


def persist_task(task: RunTask) -> None:
    state = task.public_state()
    state.pop("log_lines", None)
    write_json_atomic(state_path(task.run_id), state)


def load_persisted_task(run_id: str, directory: Path) -> RunTask | None:
    state = read_json(directory / STATE_FILE)
    report = read_json(directory / "report.json")
    if isinstance(state, dict):
        request = state.get("request") if isinstance(state.get("request"), dict) else {}
        task = RunTask(
            run_id=run_id,
            request=request,
            status=str(state.get("status") or "completed"),
            phase=str(state.get("phase") or "已完成"),
            created_at=str(state.get("created_at") or utc_now()),
            started_at=state.get("started_at"),
            ended_at=state.get("ended_at"),
            exit_code=state.get("exit_code"),
            error=state.get("error"),
            last_log=str(state.get("last_log") or ""),
        )
    elif isinstance(report, dict):
        metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
        task = RunTask(
            run_id=run_id,
            request={"scenario": metadata.get("scenario"), "mode": metadata.get("mode")},
            status="completed",
            phase="报告已生成",
            created_at=str(metadata.get("generated_at") or utc_now()),
            ended_at=str(metadata.get("generated_at") or utc_now()),
            exit_code=0,
        )
    else:
        return None

    if task.status in {"queued", "running"}:
        task.status = "interrupted"
        task.phase = "控制器重启，任务状态未知"
        task.error = "压测控制器重启前任务未完成，请根据报告和日志确认结果。"
        persist_task(task)
    return task


def get_or_load_task(run_id: str) -> RunTask | None:
    with RUNS_LOCK:
        if run_id in RUNS:
            return RUNS[run_id]
        directory = REPORTS_ROOT / run_id
        if not directory.is_dir():
            return None
        task = load_persisted_task(run_id, directory)
        if task:
            RUNS[run_id] = task
        return task


def report_for(run_id: str) -> dict[str, Any] | None:
    if not valid_run_id(run_id):
        return None
    payload = read_json(REPORTS_ROOT / run_id / "report.json")
    return payload if isinstance(payload, dict) else None


def task_response(task: RunTask, include_report: bool = False) -> dict[str, Any]:
    response = task.public_state()
    report = report_for(task.run_id)
    if report:
        metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
        response["report_metadata"] = metadata
        response["report_available"] = True
        response["report_summary"] = {
            "load": report.get("load", {}),
            "business": report.get("business", {}),
            "validation": report.get("validation", {}),
        }
        if include_report:
            response["report"] = report
    else:
        response["report_available"] = False
    response["files"] = {
        name: f"/api/performance/runs/{task.run_id}/files/{name}"
        for name in sorted(ALLOWED_FILES)
        if (task.run_directory / name).is_file()
    }
    return response


def list_tasks() -> list[dict[str, Any]]:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    with RUNS_LOCK:
        for directory in REPORTS_ROOT.iterdir():
            if directory.is_dir() and valid_run_id(directory.name):
                get_or_load_task(directory.name)
        tasks = [task_response(task) for task in RUNS.values()]
    tasks.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return tasks


def build_request(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = str(payload.get("scenario") or "product-read")
    if scenario not in SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario}")
    mode = str(payload.get("mode") or "distributed")
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")
    if payload.get("confirm_target") is not True:
        raise ValueError("confirm_target must be true before starting traffic")

    request = {
        "scenario": scenario,
        "mode": mode,
        "base_url": normalize_base_url(payload.get("base_url")),
        "product_id": parse_int(payload, "product_id", 1, 2_147_483_647),
        "initial_stock": parse_int(payload, "initial_stock", 1, 10_000_000),
        "user_id_start": parse_int(payload, "user_id_start", 1, 2_147_483_647),
        "user_count": parse_int(payload, "user_count", 1, 1_000_000),
        "convergence_wait_seconds": parse_int(payload, "convergence_wait_seconds", 0, 3600),
        "with_monitoring": bool(payload.get("with_monitoring", True)),
        "skip_reset": bool(payload.get("skip_reset", False)),
        "build": bool(payload.get("build", False)),
        "confirm_target": True,
        "compare_to": None,
    }
    compare_to = payload.get("compare_to")
    if compare_to:
        compare_to = str(compare_to)
        if not valid_run_id(compare_to):
            raise ValueError("compare_to must be a valid run id")
        if not (REPORTS_ROOT / compare_to / "report.json").is_file():
            raise ValueError("compare_to report does not exist")
        request["compare_to"] = compare_to
    return request


def make_run_id() -> str:
    prefix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    while True:
        candidate = f"{prefix}-{uuid.uuid4().hex[:6]}"
        if not (REPORTS_ROOT / candidate).exists():
            return candidate


def command_for(task: RunTask) -> list[str]:
    request = task.request
    command = [
        powershell_executable(), "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(RUN_SCRIPT),
        "-Scenario", request["scenario"], "-Mode", request["mode"],
        "-BaseUrl", request["base_url"], "-ProductId", str(request["product_id"]),
        "-InitialStock", str(request["initial_stock"]),
        "-UserIdStart", str(request["user_id_start"]),
        "-UserCount", str(request["user_count"]),
        "-ConvergenceWaitSeconds", str(request["convergence_wait_seconds"]),
        "-RunId", task.run_id, "-ConfirmTarget",
    ]
    if request.get("with_monitoring"):
        command.append("-WithMonitoring")
    if request.get("skip_reset"):
        command.append("-SkipReset")
    if not request.get("build"):
        command.append("-NoBuild")
    if request.get("compare_to"):
        command.extend(["-CompareTo", str(REPORTS_ROOT / request["compare_to"] / "report.json")])
    return command


def kill_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        process.terminate()


def run_task(task: RunTask) -> None:
    task.run_directory.mkdir(parents=True, exist_ok=True)
    with RUNS_LOCK:
        if task.stop_requested:
            task.status = "stopped"
            task.phase = "任务已停止"
            task.ended_at = utc_now()
            persist_task(task)
            return
    task.started_at = utc_now()
    task.status = "running"
    task.phase = "启动压测进程"
    persist_task(task)

    command = command_for(task)
    try:
        with task.log_path.open("a", encoding="utf-8") as log_handle:
            log_handle.write(f"$ {' '.join(command)}\n")
            log_handle.flush()
            process = subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            with RUNS_LOCK:
                task.process = process
                should_stop = task.stop_requested
            if should_stop:
                kill_process(process)
            if process.stdout is not None:
                for line in process.stdout:
                    log_handle.write(line)
                    log_handle.flush()
                    clean_line = line.strip()
                    if clean_line:
                        task.last_log = clean_line[-500:]
                        next_phase = phase_from_log(clean_line)
                        if next_phase:
                            task.phase = next_phase
                        persist_task(task)
            exit_code = process.wait()
    except OSError as exc:
        task.error = str(exc)
        task.exit_code = -1
        task.status = "failed"
        task.phase = "启动失败"
        task.ended_at = utc_now()
        persist_task(task)
        return
    finally:
        with RUNS_LOCK:
            task.process = None

    task.exit_code = exit_code
    task.ended_at = utc_now()
    if task.stop_requested:
        task.status = "stopped"
        task.phase = "任务已停止"
    elif exit_code == 0:
        task.status = "completed"
        task.phase = "测试完成"
    else:
        task.status = "failed"
        task.phase = "测试失败，但可查看已生成报告"
        task.error = f"run-test.ps1 exited with code {exit_code}"
    persist_task(task)


def stop_task(task: RunTask) -> bool:
    with RUNS_LOCK:
        process = task.process
        if task.status not in {"queued", "running"}:
            return False
        task.stop_requested = True
        task.phase = "正在停止任务"
        if process is None:
            task.status = "stopped"
            task.ended_at = utc_now()
            persist_task(task)
            return True
    kill_process(process)
    persist_task(task)
    return True


class ApiError(Exception):
    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


class PerformanceHandler(BaseHTTPRequestHandler):
    server_version = "SeckillPerformanceController/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json({"error": message, "status": status}, status)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def read_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ApiError("request body is too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ApiError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ApiError("request body must be a JSON object")
        return payload

    def do_GET(self) -> None:
        try:
            self.route_get()
        except ApiError as exc:
            self.send_error_json(exc.status, str(exc))
        except Exception as exc:  # pragma: no cover
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def do_POST(self) -> None:
        try:
            self.route_post()
        except ApiError as exc:
            self.send_error_json(exc.status, str(exc))
        except Exception as exc:  # pragma: no cover
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def route_get(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in STATIC_FILES:
            self.send_static(path)
            return
        if path == "/api/performance/health":
            self.send_json({"status": "ok", "controller": self.server_version})
            return
        if path == "/api/performance/scenarios":
            self.send_json({"scenarios": [{"name": name, **details} for name, details in SCENARIOS.items()]})
            return
        if path == "/api/performance/runs":
            self.send_json({"runs": list_tasks()})
            return

        match = re.fullmatch(r"/api/performance/runs/([^/]+)", path)
        if match:
            task = get_or_load_task(unquote(match.group(1)))
            if task is None:
                raise ApiError("run not found", HTTPStatus.NOT_FOUND)
            self.send_json(task_response(task, include_report=True))
            return

        match = re.fullmatch(r"/api/performance/runs/([^/]+)/report", path)
        if match:
            report = report_for(unquote(match.group(1)))
            if report is None:
                raise ApiError("report not found", HTTPStatus.NOT_FOUND)
            self.send_json(report)
            return

        match = re.fullmatch(r"/api/performance/runs/([^/]+)/files/([^/]+)", path)
        if match:
            self.send_run_file(unquote(match.group(1)), unquote(match.group(2)))
            return
        raise ApiError("endpoint not found", HTTPStatus.NOT_FOUND)

    def route_post(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path == "/api/performance/runs":
            try:
                request = build_request(self.read_body())
            except ValueError as exc:
                raise ApiError(str(exc)) from exc
            task = RunTask(run_id=make_run_id(), request=request)
            task.run_directory.mkdir(parents=True, exist_ok=True)
            with RUNS_LOCK:
                RUNS[task.run_id] = task
            persist_task(task)
            threading.Thread(target=run_task, args=(task,), daemon=True).start()
            self.send_json(task_response(task), HTTPStatus.ACCEPTED)
            return

        match = re.fullmatch(r"/api/performance/runs/([^/]+)/stop", path)
        if match:
            task = get_or_load_task(unquote(match.group(1)))
            if task is None:
                raise ApiError("run not found", HTTPStatus.NOT_FOUND)
            if not stop_task(task):
                raise ApiError("run is no longer active", HTTPStatus.CONFLICT)
            self.send_json(task_response(task))
            return
        raise ApiError("endpoint not found", HTTPStatus.NOT_FOUND)

    def send_static(self, path: str) -> None:
        filename, content_type = STATIC_FILES[path]
        file_path = WEB_ROOT / filename
        if not file_path.is_file():
            raise ApiError("web asset not found", HTTPStatus.NOT_FOUND)
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def send_run_file(self, run_id: str, filename: str) -> None:
        if not valid_run_id(run_id):
            raise ApiError("invalid run id", HTTPStatus.BAD_REQUEST)
        if filename not in ALLOWED_FILES:
            raise ApiError("file is not available", HTTPStatus.NOT_FOUND)
        path = REPORTS_ROOT / run_id / filename
        if not path.is_file():
            raise ApiError("file not found", HTTPStatus.NOT_FOUND)
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if filename.endswith(".json"):
            content_type = "application/json; charset=utf-8"
        elif filename.endswith(".csv"):
            content_type = "text/csv; charset=utf-8"
        elif filename.endswith(".html"):
            content_type = "text/html; charset=utf-8"
        body = path.read_bytes()
        disposition = "inline" if filename == "report.html" else "attachment"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'{disposition}; filename="{filename}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone local web controller for the performance platform.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), PerformanceHandler)
    print(f"Performance controller listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping performance controller...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

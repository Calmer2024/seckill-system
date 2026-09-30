from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPOSE_FILES = [REPO_ROOT / "docker-compose.yml"]


def compose_files(values: list[str] | None) -> list[Path]:
    if not values:
        return DEFAULT_COMPOSE_FILES
    return [Path(value).resolve() for value in values]


def compose_exec(
    files: list[Path],
    service: str,
    command: list[str],
    input_text: str | None = None,
    check: bool = True,
) -> str:
    args = ["docker", "compose"]
    for compose_file in files:
        args.extend(["-f", str(compose_file)])
    args.extend(["exec", "-T", service, *command])
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stderr.strip()}"
        )
    return result.stdout


def mysql_sql(files: list[Path], sql: str, check: bool = True) -> str:
    return compose_exec(
        files,
        "mysql-primary",
        ["mysql", "-uroot", "-p418124", "--batch", "--raw", "--skip-column-names"],
        input_text=sql,
        check=check,
    )


def mysql_rows(files: list[Path], sql: str) -> list[list[str]]:
    output = mysql_sql(files, sql)
    return [line.split("\t") for line in output.splitlines() if line.strip()]


def redis_command(files: list[Path], command: list[str], check: bool = True) -> str:
    return compose_exec(files, "redis", ["redis-cli", *command], check=check)


def sql_quote(value: object) -> str:
    text = str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"

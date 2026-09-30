from __future__ import annotations

import argparse
import csv
import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def read_json(path: str | None, default: dict) -> dict:
    if not path:
        return default
    file_path = Path(path)
    if not file_path.exists():
        return default
    return json.loads(file_path.read_text(encoding="utf-8"))


def metric_value(summary: dict, name: str, value: str, default=None):
    metric = summary.get("metrics", {}).get(name, {})
    nested_values = metric.get("values")
    if isinstance(nested_values, dict) and value in nested_values:
        return nested_values[value]
    if value in metric:
        return metric[value]
    # k6 summary-export represents Rate metrics as "value", not "rate".
    if value == "rate" and "value" in metric:
        return metric["value"]
    return default


def git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def flatten_rows(report: dict) -> list[dict[str, object]]:
    load = report["load"]
    business = report["business"]
    validation = report["validation"]
    rows = [
        {"metric": "actual_rps", "value": load.get("actual_rps"), "unit": "req/s", "source": "k6"},
        {"metric": "completed_requests", "value": load.get("completed_requests"), "unit": "requests", "source": "k6"},
        {"metric": "p50_latency", "value": load.get("p50_latency_ms"), "unit": "ms", "source": "k6"},
        {"metric": "p95_latency", "value": load.get("p95_latency_ms"), "unit": "ms", "source": "k6"},
        {"metric": "p99_latency", "value": load.get("p99_latency_ms"), "unit": "ms", "source": "k6"},
        {"metric": "http_error_rate", "value": load.get("http_error_rate"), "unit": "ratio", "source": "k6"},
        {"metric": "orders_accepted", "value": business.get("orders_accepted"), "unit": "orders", "source": "k6"},
        {"metric": "duplicate_requests", "value": business.get("duplicate_requests"), "unit": "requests", "source": "k6"},
        {"metric": "out_of_stock_requests", "value": business.get("out_of_stock_requests"), "unit": "requests", "source": "k6"},
        {"metric": "consistency_passed", "value": validation.get("passed"), "unit": "boolean", "source": "validator"},
    ]
    observability = report.get("observability", {})
    for name, value in observability.get("metrics", {}).items():
        rows.append({"metric": name, "value": value, "unit": "prometheus", "source": "prometheus"})
    for name, value in observability.get("peaks_during_run", {}).items():
        rows.append({"metric": name, "value": value, "unit": "prometheus_peak", "source": "prometheus"})
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value", "unit", "source"])
        writer.writeheader()
        writer.writerows(rows)


def write_html(path: Path, report: dict, rows: list[dict[str, object]]) -> None:
    check_rows = "".join(
        f"<tr><td>{html.escape(str(item['name']))}</td><td>{'PASS' if item['passed'] else 'FAIL'}</td>"
        f"<td>{html.escape(str(item['actual']))}</td><td>{html.escape(str(item['expected']))}</td></tr>"
        for item in report["validation"].get("checks", [])
    )
    metric_rows = "".join(
        f"<tr><td>{html.escape(str(row['metric']))}</td><td>{html.escape(str(row['value']))}</td>"
        f"<td>{html.escape(str(row['unit']))}</td><td>{html.escape(str(row['source']))}</td></tr>"
        for row in rows
    )
    status = "PASS" if report["validation"].get("passed") else "FAIL"
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Performance report {html.escape(report['metadata']['run_id'])}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#202124}}h1{{margin-bottom:4px}}table{{border-collapse:collapse;width:100%;margin:16px 0 28px}}th,td{{border:1px solid #d9dce1;padding:8px;text-align:left}}th{{background:#f3f5f7}}.pass{{color:#137333}}.fail{{color:#b3261e}}code{{word-break:break-all}}</style>
</head><body><h1>Seckill performance report</h1>
<p><strong>Run:</strong> <code>{html.escape(report['metadata']['run_id'])}</code> &nbsp; <strong>Scenario:</strong> {html.escape(report['metadata']['scenario'])} &nbsp; <strong>Mode:</strong> {html.escape(report['metadata']['mode'])}</p>
<p><strong>Generated:</strong> {html.escape(report['metadata']['generated_at'])} &nbsp; <strong>Revision:</strong> <code>{html.escape(report['metadata']['git_revision'])}</code></p>
<h2>Summary</h2><p class="{status.lower()}"><strong>Business consistency: {status}</strong></p>
<table><thead><tr><th>Metric</th><th>Value</th><th>Unit</th><th>Source</th></tr></thead><tbody>{metric_rows}</tbody></table>
<h2>Business checks</h2><table><thead><tr><th>Check</th><th>Status</th><th>Actual</th><th>Expected</th></tr></thead><tbody>{check_rows}</tbody></table>
<h2>Test boundary</h2><p>This result describes the configured local Docker environment. It is not a production capacity claim. The load generator, services, database, Redis, Kafka, and monitoring may share one Docker Desktop host.</p>
</body></html>"""
    path.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate JSON, CSV, and HTML performance reports.")
    parser.add_argument("--k6-summary", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--metrics")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--compare-to")
    args = parser.parse_args()

    summary = read_json(args.k6_summary, {})
    validation = read_json(args.validation, {"passed": False, "checks": []})
    observability = read_json(args.metrics, {"available": False, "metrics": {}})
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "metadata": {
            "run_id": args.run_id,
            "scenario": args.scenario,
            "mode": args.mode,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_revision": git_revision(),
        },
        "load": {
            "actual_rps": metric_value(summary, "http_reqs", "rate"),
            "completed_requests": metric_value(summary, "http_reqs", "count"),
            "p50_latency_ms": metric_value(
                summary,
                "http_req_duration",
                "p(50)",
                metric_value(summary, "http_req_duration", "med"),
            ),
            "p95_latency_ms": metric_value(summary, "http_req_duration", "p(95)"),
            "p99_latency_ms": metric_value(summary, "http_req_duration", "p(99)"),
            "http_error_rate": metric_value(summary, "http_req_failed", "rate"),
            "timeouts": metric_value(summary, "business_request_timeouts", "count", 0),
        },
        "business": {
            "orders_accepted": metric_value(summary, "business_orders_accepted", "count", 0),
            "duplicate_requests": metric_value(summary, "business_duplicate_requests", "count", 0),
            "out_of_stock_requests": metric_value(summary, "business_out_of_stock_requests", "count", 0),
            "rejected_requests": metric_value(summary, "business_rejected_requests", "count", 0),
            "auth_failures": metric_value(summary, "business_auth_failures", "count", 0),
            "business_success_rate": metric_value(summary, "business_order_success_rate", "rate"),
        },
        "validation": validation,
        "observability": observability,
    }

    if args.compare_to:
        baseline = read_json(args.compare_to, {})
        report["comparison"] = compare_reports(report, baseline)

    rows = flatten_rows(report)
    json_path = output_dir / "report.json"
    csv_path = output_dir / "report.csv"
    html_path = output_dir / "report.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, rows)
    write_html(html_path, report, rows)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "html": str(html_path)}, ensure_ascii=False))


def compare_reports(current: dict, baseline: dict) -> dict:
    current_load = current.get("load", {})
    baseline_load = baseline.get("load", {})
    metric_pairs = [
        ("actual_rps", "higher_is_better"),
        ("p95_latency_ms", "lower_is_better"),
        ("p99_latency_ms", "lower_is_better"),
        ("http_error_rate", "lower_is_better"),
    ]
    comparison = {}
    for metric, direction in metric_pairs:
        current_value = current_load.get(metric)
        baseline_value = baseline_load.get(metric)
        improvement = None
        if isinstance(current_value, (int, float)) and isinstance(baseline_value, (int, float)) and baseline_value != 0:
            improvement = (current_value - baseline_value) / abs(baseline_value)
            if direction == "lower_is_better":
                improvement = -improvement
        comparison[metric] = {
            "current": current_value,
            "baseline": baseline_value,
            "improvement_ratio": improvement,
            "direction": direction,
        }
    return comparison


if __name__ == "__main__":
    main()

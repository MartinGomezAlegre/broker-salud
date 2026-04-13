import argparse
import json
import math
import os
import queue
import ssl
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_template(value: str) -> str:
    result = value
    for key, env_value in os.environ.items():
        result = result.replace("${" + key + "}", env_value)
    return result


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return values[lower]
    weight = rank - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def run_scenario(base_url: str, scenario: dict, timeout: float) -> dict:
    total_requests = int(scenario.get("requests", 100))
    concurrency = int(scenario.get("concurrency", 10))
    method = str(scenario.get("method", "GET")).upper()
    path = str(scenario["path"])
    name = str(scenario.get("name", path))
    headers = {key: resolve_template(str(value)) for key, value in scenario.get("headers", {}).items()}
    body = scenario.get("json_body")
    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    request_queue: queue.Queue[int] = queue.Queue()
    for index in range(total_requests):
        request_queue.put(index)

    latencies: list[float] = []
    status_codes: dict[str, int] = {}
    errors: dict[str, int] = {}
    bytes_received = 0
    lock = threading.Lock()
    target_url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    ssl_context = ssl.create_default_context()
    started_at = time.perf_counter()

    def worker() -> None:
        nonlocal bytes_received
        while True:
            try:
                request_queue.get_nowait()
            except queue.Empty:
                return

            started = time.perf_counter()
            try:
                request = urllib.request.Request(
                    target_url,
                    headers=headers,
                    method=method,
                    data=data,
                )
                with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
                    payload = response.read()
                    latency_ms = (time.perf_counter() - started) * 1000
                    status = str(response.status)
                    with lock:
                        latencies.append(latency_ms)
                        status_codes[status] = status_codes.get(status, 0) + 1
                        bytes_received += len(payload)
            except urllib.error.HTTPError as exc:
                latency_ms = (time.perf_counter() - started) * 1000
                with lock:
                    latencies.append(latency_ms)
                    status = str(exc.code)
                    status_codes[status] = status_codes.get(status, 0) + 1
            except Exception as exc:  # noqa: BLE001
                with lock:
                    key = type(exc).__name__
                    errors[key] = errors.get(key, 0) + 1
            finally:
                request_queue.task_done()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    total_seconds = max(time.perf_counter() - started_at, 0.001)
    ordered_latencies = sorted(latencies)

    return {
        "name": name,
        "method": method,
        "path": path,
        "requests": total_requests,
        "concurrency": concurrency,
        "duration_seconds": round(total_seconds, 3),
        "requests_per_second": round(total_requests / total_seconds, 2),
        "success_rate": round((sum(int(code) < 400 for code in status_codes for _ in range(status_codes[code])) / total_requests) * 100, 2),
        "latency_ms": {
            "min": round(ordered_latencies[0], 2) if ordered_latencies else 0.0,
            "avg": round(statistics.mean(ordered_latencies), 2) if ordered_latencies else 0.0,
            "p50": round(percentile(ordered_latencies, 0.50), 2),
            "p95": round(percentile(ordered_latencies, 0.95), 2),
            "p99": round(percentile(ordered_latencies, 0.99), 2),
            "max": round(ordered_latencies[-1], 2) if ordered_latencies else 0.0,
        },
        "status_codes": status_codes,
        "errors": errors,
        "bytes_received": bytes_received,
    }


def render_markdown(base_url: str, results: list[dict]) -> str:
    lines = [
        "# Capacity Report",
        "",
        f"Base URL: `{base_url}`",
        "",
        "| Scenario | Req | Conc | RPS | Success % | p50 ms | p95 ms | p99 ms | Max ms | Status codes | Errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in results:
        latency = item["latency_ms"]
        status_codes = ", ".join(f"{code}:{count}" for code, count in sorted(item["status_codes"].items()))
        errors = ", ".join(f"{name}:{count}" for name, count in sorted(item["errors"].items())) or "-"
        lines.append(
            f"| {item['name']} | {item['requests']} | {item['concurrency']} | {item['requests_per_second']} | "
            f"{item['success_rate']} | {latency['p50']} | {latency['p95']} | {latency['p99']} | {latency['max']} | "
            f"{status_codes or '-'} | {errors} |"
        )
    lines.extend(
        [
            "",
            "## Reading guide",
            "",
            "- `Success %` below 99 means the endpoint is already degrading under that load.",
            "- `p95` is the best indicator of user-perceived slowness under pressure.",
            "- `p99` and `Max` help identify long-tail spikes that are usually hidden by averages.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight HTTP capacity checks.")
    parser.add_argument("--base-url", required=True, help="Public base URL to benchmark, e.g. https://celdoctor-waitlist.vercel.app")
    parser.add_argument(
        "--scenarios",
        default=str(Path(__file__).with_name("scenarios.example.json")),
        help="JSON file with benchmark scenarios.",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds.")
    parser.add_argument("--json-out", help="Optional path to write raw JSON results.")
    parser.add_argument("--markdown-out", help="Optional path to write a Markdown summary.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv_file(repo_root / ".env")

    scenarios = json.loads(Path(args.scenarios).read_text(encoding="utf-8"))
    results = [run_scenario(args.base_url, scenario, args.timeout) for scenario in scenarios]

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(args.base_url, results), encoding="utf-8")

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

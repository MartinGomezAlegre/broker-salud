import argparse
import json
import os
import statistics
import time
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


def timed_query(cursor, sql: str, params=None, iterations: int = 3) -> dict:
    latencies = []
    sample = None
    for _ in range(iterations):
        started = time.perf_counter()
        cursor.execute(sql, params or ())
        try:
            sample = cursor.fetchone()
        except Exception:  # noqa: BLE001
            sample = None
        latencies.append((time.perf_counter() - started) * 1000)
    return {
        "avg_ms": round(statistics.mean(latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "sample": sample[0] if sample else None,
    }


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,),
    )
    return bool(cursor.fetchone()[0])


def run_write_benchmark(cursor, rows: int, batch_size: int) -> dict:
    cursor.execute("CREATE TEMP TABLE IF NOT EXISTS capacity_probe (id SERIAL PRIMARY KEY, payload TEXT)")
    payload = "x" * 128
    started = time.perf_counter()
    inserted = 0
    while inserted < rows:
        current_batch = min(batch_size, rows - inserted)
        values = [(payload,) for _ in range(current_batch)]
        cursor.executemany("INSERT INTO capacity_probe (payload) VALUES (%s)", values)
        inserted += current_batch
    elapsed = max(time.perf_counter() - started, 0.001)
    return {
        "rows": rows,
        "batch_size": batch_size,
        "duration_seconds": round(elapsed, 3),
        "rows_per_second": round(rows / elapsed, 2),
    }


def render_markdown(database_label: str, counts: dict, query_results: dict, write_result: dict | None) -> str:
    lines = [
        "# Database Capacity Snapshot",
        "",
        f"Database source: `{database_label}`",
        "",
        "## Table counts",
        "",
        "| Table | Rows |",
        "| --- | ---: |",
    ]
    for table, value in counts.items():
        lines.append(f"| {table} | {value} |")

    lines.extend(
        [
            "",
            "## Read latency",
            "",
            "| Probe | Avg ms | Min ms | Max ms | Sample |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for name, result in query_results.items():
        lines.append(
            f"| {name} | {result['avg_ms']} | {result['min_ms']} | {result['max_ms']} | {result['sample']} |"
        )

    if write_result:
        lines.extend(
            [
                "",
                "## Temp write benchmark",
                "",
                "| Rows | Batch | Seconds | Rows/sec |",
                "| ---: | ---: | ---: | ---: |",
                f"| {write_result['rows']} | {write_result['batch_size']} | {write_result['duration_seconds']} | {write_result['rows_per_second']} |",
                "",
                "- This benchmark uses a session-local temp table, so it does not persist data.",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a read-only database probe plus an optional temp-table write test.")
    parser.add_argument("--database-url", help="Full PostgreSQL connection string. If omitted, DATABASE_URL from env is used.")
    parser.add_argument("--json-out", help="Optional path to write raw JSON results.")
    parser.add_argument("--markdown-out", help="Optional path to write a Markdown summary.")
    parser.add_argument("--run-write-benchmark", action="store_true", help="Run a temp-table insert benchmark.")
    parser.add_argument("--write-rows", type=int, default=5000, help="Number of temp rows to insert when write benchmark is enabled.")
    parser.add_argument("--batch-size", type=int, default=250, help="Batch size for the temp write benchmark.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv_file(repo_root / ".env")
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL no esta configurada.")

    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("psycopg2 no esta disponible en este entorno.") from exc

    counts = {}
    query_results = {}
    write_result = None
    critical_tables = ["usuarios", "suscripciones", "tickets_soporte", "pagos", "empresas", "beneficiarios"]

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for table in critical_tables:
                if table_exists(cursor, table):
                    counts[table] = timed_query(cursor, f"SELECT COUNT(*) FROM {table}")["sample"]
                else:
                    counts[table] = "missing"

            if table_exists(cursor, "usuarios"):
                query_results["usuarios_count"] = timed_query(cursor, "SELECT COUNT(*) FROM usuarios")
                sample_login = timed_query(
                    cursor,
                    """
                    SELECT id
                    FROM usuarios
                    WHERE email LIKE 'perf_user_%%@example.com'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                )
                if sample_login["sample"] is not None:
                    query_results["login_lookup_by_email"] = timed_query(
                        cursor,
                        """
                        SELECT id, password_hash, rol, activo
                        FROM usuarios
                        WHERE email = (
                            SELECT email
                            FROM usuarios
                            WHERE email LIKE 'perf_user_%%@example.com'
                            ORDER BY id DESC
                            LIMIT 1
                        )
                        """,
                    )
            if table_exists(cursor, "suscripciones"):
                query_results["suscripciones_activas"] = timed_query(
                    cursor,
                    "SELECT COUNT(*) FROM suscripciones WHERE estado IN ('activa', 'cancelacion_programada')",
                )
                query_results["mi_suscripcion_lookup"] = timed_query(
                    cursor,
                    """
                    SELECT s.id
                    FROM suscripciones s
                    JOIN usuarios u ON u.id = s.usuario_id
                    WHERE u.email = (
                        SELECT email
                        FROM usuarios
                        WHERE email LIKE 'perf_user_%%@example.com'
                        ORDER BY id DESC
                        LIMIT 1
                    )
                      AND s.estado NOT IN ('cancelada', 'vencida')
                    ORDER BY
                        CASE s.estado
                            WHEN 'activa' THEN 1
                            WHEN 'cancelacion_programada' THEN 2
                            WHEN 'pendiente_pago' THEN 3
                            ELSE 4
                        END,
                        COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                        s.created_at DESC
                    LIMIT 1
                    """,
                )
            if table_exists(cursor, "tickets_soporte"):
                query_results["tickets_abiertos"] = timed_query(
                    cursor,
                    """
                    SELECT COUNT(*)
                    FROM tickets_soporte
                    WHERE estado IS NULL OR estado = '' OR estado IN ('nuevo', 'abierto')
                    """,
                )
            if table_exists(cursor, "pagos"):
                query_results["pagos_ultimos_30_dias"] = timed_query(
                    cursor,
                    "SELECT COUNT(*) FROM pagos WHERE created_at >= NOW() - INTERVAL '30 days'",
                )

            if args.run_write_benchmark:
                write_result = run_write_benchmark(cursor, args.write_rows, args.batch_size)
                connection.rollback()

    result = {
        "counts": counts,
        "queries": query_results,
        "write_benchmark": write_result,
    }

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(
            render_markdown("DATABASE_URL", counts, query_results, write_result),
            encoding="utf-8",
        )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

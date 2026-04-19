import re
import unicodedata
from secrets import token_hex

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

COMMISSIONABLE_STATES = ("activa", "cancelacion_programada")

REQUIRED_TABLES = {
    "brokers",
    "broker_sellers",
    "direct_sellers",
    "commission_liquidations",
}

REQUIRED_SUSCRIPCION_COLUMNS = {
    "referral_code",
    "broker_seller_id",
    "direct_seller_id",
}


def ensure_commercial_schema(db: Session):
    tables = db.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = ANY(:tables)
    """), {"tables": list(REQUIRED_TABLES)}).fetchall()

    found_tables = {row.table_name for row in tables}
    missing_tables = REQUIRED_TABLES - found_tables

    columns = db.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'suscripciones'
          AND column_name = ANY(:columns)
    """), {"columns": list(REQUIRED_SUSCRIPCION_COLUMNS)}).fetchall()
    found_columns = {row.column_name for row in columns}
    missing_columns = REQUIRED_SUSCRIPCION_COLUMNS - found_columns

    if missing_tables or missing_columns:
        missing_parts: list[str] = []
        if missing_tables:
            missing_parts.append(f"tablas faltantes: {', '.join(sorted(missing_tables))}")
        if missing_columns:
            missing_parts.append(
                f"columnas faltantes en suscripciones: {', '.join(sorted(missing_columns))}"
            )

        raise HTTPException(
            status_code=503,
            detail=(
                "El modulo comercial no esta migrado en la base de datos. Ejecuta alembic upgrade head. "
                + "; ".join(missing_parts)
            ),
        )


def generate_referral_code(
    db: Session,
    source: str,
    exclude_table: str | None = None,
    exclude_id: int | None = None,
) -> str:
    base = _slugify(source)[:10] or f"CD{token_hex(2).upper()}"
    base = base.upper()

    for index in range(0, 100):
        suffix = "" if index == 0 else f"{index + 1:02d}"
        candidate = f"{base}{suffix}"[:20]
        if not referral_code_exists(db, candidate, exclude_table, exclude_id):
            return candidate

    while True:
        candidate = f"{base[:6]}{token_hex(3).upper()}"
        if not referral_code_exists(db, candidate, exclude_table, exclude_id):
            return candidate


def referral_code_exists(
    db: Session,
    code: str,
    exclude_table: str | None = None,
    exclude_id: int | None = None,
) -> bool:
    checks = []
    params = {"code": code}

    for table in ("direct_sellers", "broker_sellers"):
        clause = f"SELECT 1 FROM {table} WHERE referral_code = :code"
        if exclude_table == table and exclude_id is not None:
            clause += " AND id <> :exclude_id"
            params["exclude_id"] = exclude_id
        checks.append(f"EXISTS ({clause})")

    row = db.execute(text(f"SELECT {' OR '.join(checks)} AS exists_code"), params).fetchone()
    return bool(row and row.exists_code)


def compute_commission_sql(
    amount_sql: str,
    commission_type_sql: str,
    commission_value_sql: str,
) -> str:
    return (
        f"CASE WHEN {commission_type_sql} = 'fijo' "
        f"THEN {commission_value_sql} "
        f"ELSE COALESCE({amount_sql}, 0) * {commission_value_sql} / 100.0 END"
    )


def _slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "", ascii_value).strip()

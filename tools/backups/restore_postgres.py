from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restaura un backup logico de PostgreSQL generado por pg_dump custom usando pg_restore.",
    )
    parser.add_argument("backup_file", help="Ruta al archivo .dump")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Base destino. Si no se indica, usa DATABASE_URL.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma automaticamente la restauracion.",
    )
    return parser.parse_args()


def ensure_pg_restore() -> str:
    executable = shutil.which("pg_restore")
    if not executable:
        raise RuntimeError(
            "No encontramos pg_restore en el PATH. Instala PostgreSQL client tools o agrega pg_restore al PATH.",
        )
    return executable


def ensure_database_url(database_url: str | None) -> str:
    if not database_url:
        raise RuntimeError("Falta DATABASE_URL. Pasa --database-url o configura la variable de entorno.")
    return database_url


def main() -> int:
    try:
        args = parse_args()
        database_url = ensure_database_url(args.database_url)
        pg_restore = ensure_pg_restore()
        backup_file = Path(args.backup_file).resolve()

        if not backup_file.exists():
            raise RuntimeError(f"No existe el archivo de backup: {backup_file}")

        if not args.yes:
            sys.stderr.write(
                "Esta operacion puede sobreescribir datos existentes. Reejecuta con --yes para confirmar.\n",
            )
            return 1

        command = [
            pg_restore,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            database_url,
            str(backup_file),
        ]

        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr or "pg_restore devolvio un error.\n")
            return completed.returncode or 1

        print(f"Restore completado desde {backup_file.name}")
        return 0
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

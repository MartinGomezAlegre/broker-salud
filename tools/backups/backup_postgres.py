from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un backup logico de PostgreSQL usando pg_dump en formato custom.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Connection string de PostgreSQL. Si no se indica, usa DATABASE_URL.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("BACKUP_OUTPUT_DIR", "backups"),
        help="Directorio donde se guardaran los dumps.",
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("BACKUP_FILE_PREFIX", "celdoctor"),
        help="Prefijo del archivo de backup.",
    )
    parser.add_argument(
        "--label",
        default=os.getenv("BACKUP_LABEL", "manual"),
        help="Etiqueta corta para identificar el backup.",
    )
    return parser.parse_args()


def ensure_pg_dump() -> str:
    executable = shutil.which("pg_dump")
    if not executable:
        raise RuntimeError(
            "No encontramos pg_dump en el PATH. Instala PostgreSQL client tools o agrega pg_dump al PATH.",
        )
    return executable


def ensure_database_url(database_url: str | None) -> str:
    if not database_url:
        raise RuntimeError("Falta DATABASE_URL. Pasa --database-url o configura la variable de entorno.")
    return database_url


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    try:
        args = parse_args()
        database_url = ensure_database_url(args.database_url)
        pg_dump = ensure_pg_dump()

        output_dir = Path(args.output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in args.label)
        filename = f"{args.prefix}_{safe_label}_{timestamp}.dump"
        dump_path = output_dir / filename

        command = [
            pg_dump,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            database_url,
            "--file",
            str(dump_path),
        ]

        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr or "pg_dump devolvio un error.\n")
            return completed.returncode or 1

        checksum = sha256sum(dump_path)
        checksum_path = dump_path.with_suffix(dump_path.suffix + ".sha256")
        checksum_path.write_text(f"{checksum}  {dump_path.name}\n", encoding="utf-8")

        metadata = {
            "created_at": datetime.now().isoformat(),
            "file": dump_path.name,
            "label": args.label,
            "sha256": checksum,
            "size_bytes": dump_path.stat().st_size,
            "output_dir": str(output_dir),
        }
        metadata_path = dump_path.with_suffix(dump_path.suffix + ".json")
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        print(json.dumps(metadata, indent=2))
        return 0
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

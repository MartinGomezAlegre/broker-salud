from __future__ import annotations

import json
import os
import re
import subprocess
import sys


EXCLUDE_PATTERN = re.compile(
    r"(^venv/|^\.git/|^__pycache__/|^alembic/versions/__pycache__/|^app/__pycache__/|^tools/capacity/)"
)
IGNORED_TRACKED_FILES = {
    ".env.example",
    "README.md",
}


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "No se pudo listar archivos versionados")

    files = []
    for raw_path in result.stdout.splitlines():
        path = raw_path.strip()
        if not path:
            continue
        if path in IGNORED_TRACKED_FILES:
            continue
        if EXCLUDE_PATTERN.search(path):
            continue
        files.append(path)

    return files


def main() -> int:
    detect_secrets_executable = os.path.join(
        os.path.dirname(sys.executable),
        "detect-secrets.exe" if os.name == "nt" else "detect-secrets",
    )
    tracked_files = _tracked_files()

    if not tracked_files:
        print("detect-secrets sin archivos para escanear")
        return 0

    result = subprocess.run(
        [
            detect_secrets_executable,
            "scan",
            "--force-use-all-plugins",
            *tracked_files,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        sys.stderr.write(result.stderr or result.stdout)
        return result.returncode

    payload = json.loads(result.stdout)
    findings = payload.get("results", {})

    if findings:
        sys.stderr.write("detect-secrets encontro hallazgos potenciales:\n")
        for file_path, matches in findings.items():
            sys.stderr.write(f"- {file_path}: {len(matches)} hallazgo(s)\n")
        return 1

    print("detect-secrets sin hallazgos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

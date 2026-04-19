from __future__ import annotations

import json
import subprocess
import sys


EXCLUDE_PATTERN = r"(^venv/|^\.git/|^__pycache__/|^alembic/versions/__pycache__/|^app/__pycache__/|^tools/capacity/)"


def main() -> int:
    result = subprocess.run(
        [
            "detect-secrets",
            "scan",
            "--all-files",
            "--force-use-all-plugins",
            "--exclude-files",
            EXCLUDE_PATTERN,
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

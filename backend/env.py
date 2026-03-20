from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(dotenv_path: Path) -> None:
    """Load simple KEY=VALUE pairs from a .env file into os.environ.

    - Existing environment variables are NOT overwritten.
    - Lines starting with # are ignored.
    - Quotes around values are stripped.

    This is intentionally small to avoid extra dependencies.
    """

    try:
        if not dotenv_path.exists():
            return

        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.lower().startswith("export "):
                line = line[7:].strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"").strip("'")

            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        # If the file can't be read, just continue with process env.
        return

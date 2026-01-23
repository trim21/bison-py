from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from ._version import BISON_VERSION, __version__

_PACKAGE_ROOT = Path(__file__).resolve().parent


def get_data_root() -> Path:
    """Return the root directory containing the bundled Bison payload."""
    override = os.environ.get("BISON_BIN_ROOT")
    if override:
        return Path(override)
    return _PACKAGE_ROOT / "_bison"


def get_binary_path() -> str:
    """Return the path to the bundled bison executable."""
    override = os.environ.get("BISON_BIN_PATH")
    if override:
        return override
    candidate = get_data_root() / "bin" / "bison"
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError("Bundled bison binary is missing; reinstall bison-bin")


def run_version() -> str:
    """Run the bundled bison --version and return stdout."""
    cmd = [get_binary_path(), "--version"]
    try:
        out = subprocess.check_output(cmd, text=True)
        return out.strip()
    except FileNotFoundError as exc:  # pragma: no cover - runtime guard
        raise FileNotFoundError("bison executable not found") from exc


def ensure_runtime() -> None:
    """Best-effort check that the bundled binary is executable."""
    binary = get_binary_path()
    if not os.access(binary, os.X_OK):
        # Try to set executable bit if possible.
        mode = os.stat(binary).st_mode
        os.chmod(binary, mode | 0o111)


def find_yacc_link() -> Optional[str]:
    """Return the path to the yacc compatibility shim if present."""
    yacc_path = get_data_root() / "bin" / "yacc"
    if yacc_path.exists():
        return str(yacc_path)
    return None


__all__ = [
    "BISON_VERSION",
    "__version__",
    "ensure_runtime",
    "find_yacc_link",
    "get_binary_path",
    "get_data_root",
    "run_version",
]

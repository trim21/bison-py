import os
import sys
from pathlib import Path

from . import get_binary_path, get_yacc_path


def _exec(binary: Path, argv: "list[str]") -> None:
    # Replace current process with the packaged binary to preserve signals/exit codes.
    os.execve(str(binary), [binary.name, *argv], os.environ.copy())


def main_bison() -> None:
    binary = get_binary_path()
    if not binary.exists():
        sys.exit(f"bison binary not found at {binary}")
    _exec(binary, sys.argv[1:])


def main_yacc() -> None:
    binary = get_yacc_path()
    if not binary.exists():
        sys.exit(f"yacc binary not found at {binary}")
    _exec(binary, sys.argv[1:])

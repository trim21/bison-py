from pathlib import Path

__all__ = ["get_payload_root", "get_binary_path", "get_yacc_path"]


def get_payload_root() -> Path:
    """Return the root directory containing the packaged bison payload."""
    return Path(__file__).resolve().parent / "_payload"


def get_binary_path() -> Path:
    """Return the path to the packaged bison executable."""
    return get_payload_root() / "bin" / "bison"


def get_yacc_path() -> Path:
    """Return the path to the packaged yacc executable."""
    return get_payload_root() / "bin" / "yacc"

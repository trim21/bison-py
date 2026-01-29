import os
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any, Optional

from pdm.backend.hooks import Context
import requests

PROJECT_ROOT = Path(__file__).parent
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_BISON_FALLBACK = "3.8.2"
BISON_TARBALL = f"bison-{DEFAULT_BISON_FALLBACK}.tar.xz"
BISON_URL = f"https://ftp.gnu.org/gnu/bison/{BISON_TARBALL}"
VENDORED_TARBALL = SRC_ROOT / "bison_bin" / "_sources" / BISON_TARBALL
CACHE_TARBALL_DIRNAME = "bison-source-cache"

machine = platform.machine().lower()
if machine in {"x86_64", "amd64"}:
    arch = "x64"
elif machine in {"aarch64", "arm64"}:
    arch = "aarch64"
elif machine in {"i386", "i486", "i586", "i686", "x86"}:
    arch = "x86"
else:
    raise Exception("unsupported arch {}".format(machine))


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("downloading", url)
    resp = requests.get(url, timeout=600)
    with open(dest, "wb") as fh:
        fh.write(resp.content)


def _extract(archive: Path, target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tf:
        tf.extractall(target)
        tops = {Path(member.name).parts[0] for member in tf.getmembers() if member.name}
    roots = [target / name for name in tops if (target / name).exists()]
    if len(roots) == 1:
        return roots[0]
    return target


def _run(cmd: list[str], *, cwd: Path, env: "dict[str, str]") -> None:
    print("run: ", shlex.join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd), env=env)


def _build_tar_project(
    *,
    project: str,
    archive: Path,
    workdir: Path,
    prefix: Path,
    env: "dict[str, str]",
    extra_config: "Optional[list[str]]" = None,
) -> None:
    src_root = _extract(archive, workdir)
    configure = src_root / "configure"
    if not configure.exists():
        raise RuntimeError(f"Missing configure script for {project}")

    prefix.mkdir(parents=True, exist_ok=True)
    config_args = [f"--prefix={prefix}"]
    if extra_config:
        config_args.extend(extra_config)

    _run(["bash", "./configure", *config_args], cwd=src_root, env=env)
    _run(["make"], cwd=src_root, env=env)
    _run(["make", "install"], cwd=src_root, env=env)


def _ensure_vendored_tarball() -> Path:
    if VENDORED_TARBALL.exists():
        return VENDORED_TARBALL

    VENDORED_TARBALL.parent.mkdir(parents=True, exist_ok=True)
    _download(BISON_URL, VENDORED_TARBALL)
    return VENDORED_TARBALL


def _resolve_tarball(downloads: Path) -> Path:
    if VENDORED_TARBALL.exists():
        return VENDORED_TARBALL

    archive_path = downloads / BISON_TARBALL
    if not archive_path.exists():
        _download(BISON_URL, archive_path)
    return archive_path


def build_bison(
    stage_root: Path,
    install_prefix: Path,
    *,
    archive: "Path | None" = None,
) -> Path:
    env = os.environ.copy()

    downloads = stage_root / "downloads"
    workdir = stage_root / "work"

    if stage_root.exists():
        shutil.rmtree(stage_root)
    workdir.mkdir(parents=True, exist_ok=True)
    downloads.mkdir(parents=True, exist_ok=True)

    env = env.copy()

    if sys.platform == "linux":
        if arch == "x64":
            env["CC"] = "zig cc -target x86_64-linux-musl"
        elif arch == "aarch64":
            env["CC"] = "zig cc -target aarch64-linux-musl"
        elif arch == "x86":
            env["CC"] = "zig cc -target x86-linux-musl"
        else:
            raise Exception(f"unknown arch {platform.machine()}")

    archive_path = archive or _resolve_tarball(downloads)

    _build_tar_project(
        project="bison",
        archive=archive_path,
        workdir=workdir,
        prefix=install_prefix,
        env=env,
        extra_config=[
            "--disable-nls",
            "--enable-relocatable",
        ],
    )

    return install_prefix


def _default_linux_plat_name() -> "str | None":
    if not sys.platform.startswith("linux"):
        return None

    plats = {
        "x64": "manylinux_2_12_x86_64.manylinux2010_x86_64.musllinux_1_1_x86_64",
        "aarch64": "manylinux_2_17_aarch64.manylinux2014_aarch64.musllinux_1_1_aarch64",
        "x86": "manylinux_2_12_i686.manylinux2010_i686.musllinux_1_1_i686",
    }

    try:
        return plats[arch]
    except KeyError:
        raise RuntimeError(f"No plat-name mapping for {arch}") from None


def pdm_build_hook_enabled(context: Context):
    return True


def pdm_build_initialize(context: Context) -> None:
    if context.target == "sdist":
        _ensure_vendored_tarball()
        return

    config_settings: "dict[str, Any]" = {
        "--python-tag": "py3",
        "--py-limited-api": "none",
        **context.builder.config_settings,
    }

    linux_plat_name = _default_linux_plat_name()
    if linux_plat_name is not None:
        config_settings["--plat-name"] = linux_plat_name

    context.builder.config_settings = config_settings

    try:
        shutil.rmtree(context.build_dir)
    except FileNotFoundError:
        pass

    context.ensure_build_dir()
    stage_root = Path(context.build_dir) / "bison-stage"
    payload_prefix = Path(context.build_dir) / "bison_bin" / "_payload"

    cache_tarball = Path(context.build_dir) / CACHE_TARBALL_DIRNAME / BISON_TARBALL
    cache_tarball.parent.mkdir(parents=True, exist_ok=True)

    if VENDORED_TARBALL.exists():
        shutil.copy(VENDORED_TARBALL, cache_tarball)
        VENDORED_TARBALL.unlink()
        # Best-effort cleanup of empty _sources directory.
        try:
            VENDORED_TARBALL.parent.rmdir()
        except OSError:
            pass
    elif not cache_tarball.exists():
        _download(BISON_URL, cache_tarball)

    build_bison(stage_root, payload_prefix, archive=cache_tarball)

    stage_root = Path(context.build_dir) / "bison-stage"
    if stage_root.exists():
        shutil.rmtree(stage_root, ignore_errors=True)


def pdm_build_finalize(context: Context, artifact: Path) -> None:
    pass

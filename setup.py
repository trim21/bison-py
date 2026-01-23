from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Optional
from urllib.request import urlopen

from setuptools import Command, Distribution, find_packages, setup
from setuptools.command.build_py import build_py

PROJECT_ROOT = Path(__file__).parent
DEFAULT_M4_VERSION = "1.4.19"
DEFAULT_BISON_FALLBACK = "3.8.2"


def _version_key(ver: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", ver))


def discover_latest(project: str, fallback: str) -> str:
    url = f"https://ftp.gnu.org/gnu/{project}/"
    try:
        with urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8", "replace")
    except Exception:
        return fallback
    pattern = re.compile(rf"{project}-(\d+\.\d+(?:\.\d+)?)\.tar\.(?:gz|bz2|xz)")
    versions = {match.group(1) for match in pattern.finditer(body)}
    if not versions:
        return fallback
    return sorted(versions, key=_version_key)[-1]


BISON_VERSION = os.environ.get("BISON_VERSION") or discover_latest(
    "bison", DEFAULT_BISON_FALLBACK
)
M4_VERSION = os.environ.get("M4_VERSION") or DEFAULT_M4_VERSION
PACKAGE_VERSION = os.environ.get("BISON_BIN_VERSION") or BISON_VERSION


class build_bison(Command):
    description = "Build and stage GNU Bison plus dependencies"
    user_options: list[tuple[str, Optional[str], str]] = []

    def initialize_options(self) -> None:
        self.build_temp = None

    def finalize_options(self) -> None:
        build_cmd = self.get_finalized_command("build")
        self.build_temp = build_cmd.build_temp

    def run(self) -> None:
        stage_root = Path(self.build_temp).resolve() / "bison-stage"
        downloads = stage_root / "downloads"
        workdir = stage_root / "work"
        prefix = stage_root / "install"
        env = os.environ.copy()
        parallel = int(env.get("BISON_BUILD_PARALLEL", "4"))

        if stage_root.exists():
            shutil.rmtree(stage_root)
        workdir.mkdir(parents=True, exist_ok=True)
        downloads.mkdir(parents=True, exist_ok=True)

        m4_prefix = stage_root / "m4"
        self._build_tar_project(
            project="m4",
            version=M4_VERSION,
            url=f"https://ftp.gnu.org/gnu/m4/m4-{M4_VERSION}.tar.xz",
            downloads=downloads,
            workdir=workdir,
            prefix=m4_prefix,
            env=env,
            parallel=parallel,
            extra_config=["--disable-dependency-tracking", "--enable-static", "--enable-shared"],
        )

        env["PATH"] = f"{m4_prefix / 'bin'}:{env.get('PATH', '')}"
        env["M4"] = str(m4_prefix / "bin" / "m4")

        self._build_tar_project(
            project="bison",
            version=BISON_VERSION,
            url=f"https://ftp.gnu.org/gnu/bison/bison-{BISON_VERSION}.tar.xz",
            downloads=downloads,
            workdir=workdir,
            prefix=prefix,
            env=env,
            parallel=parallel,
            extra_config=["--disable-nls"],
        )

        if env.get("BISON_BIN_STRIP") == "1":
            self._strip_binaries(prefix)

        self.distribution.bison_stage_dir = str(prefix)
        self.distribution.bison_version = BISON_VERSION

    def _strip_binaries(self, prefix: Path) -> None:
        strip_cmd = shutil.which("strip")
        if not strip_cmd:
            return
        for binary in (prefix / "bin").glob("*"):
            if binary.is_file():
                try:
                    subprocess.check_call([strip_cmd, str(binary)])
                except subprocess.CalledProcessError:
                    # Non-fatal; keep unstripped binary.
                    continue

    def _download(self, url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(url) as resp, open(dest, "wb") as fh:
            shutil.copyfileobj(resp, fh)

    def _extract(self, archive: Path, target: Path) -> Path:
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

    def _build_tar_project(
        self,
        *,
        project: str,
        version: str,
        url: str,
        downloads: Path,
        workdir: Path,
        prefix: Path,
        env: dict[str, str],
        parallel: int,
        extra_config: Optional[list[str]] = None,
    ) -> None:
        archive_path = downloads / f"{project}-{version}.tar.xz"
        if not archive_path.exists():
            self.announce(f"Downloading {project} {version}", level=2)
            self._download(url, archive_path)

        src_root = self._extract(archive_path, workdir)
        configure = src_root / "configure"
        if not configure.exists():
            raise RuntimeError(f"Missing configure script for {project}")

        prefix.mkdir(parents=True, exist_ok=True)
        config_args = [f"--prefix={prefix}"]
        if extra_config:
            config_args.extend(extra_config)

        self._run(["bash", "./configure", *config_args], cwd=src_root, env=env)
        self._run(["make", f"-j{parallel}"], cwd=src_root, env=env)
        self._run(["make", "install"], cwd=src_root, env=env)

    def _run(self, cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
        subprocess.check_call(cmd, cwd=str(cwd), env=env)


class BuildPyWithBison(build_py):
    def run(self) -> None:
        self.run_command("build_bison")
        super().run()

        stage_dir = Path(getattr(self.distribution, "bison_stage_dir"))
        target_root = Path(self.build_lib) / "bison_bin" / "_bison"
        if target_root.exists():
            shutil.rmtree(target_root)
        shutil.copytree(stage_dir, target_root)

        version_py = Path(self.build_lib) / "bison_bin" / "_version.py"
        version_py.parent.mkdir(parents=True, exist_ok=True)
        version_py.write_text(
            f'__version__ = "{PACKAGE_VERSION}"\nBISON_VERSION = "{BISON_VERSION}"\n',
            encoding="utf-8",
        )

        generated = [str(p) for p in target_root.rglob("*") if p.is_file()]
        generated.append(str(version_py))
        self._generated_outputs = generated

        bin_dir = target_root / "bin"
        bin_files = [str(p) for p in bin_dir.glob("*") if p.is_file()]
        # Install the raw executables into PREFIX/bin via data_files.
        existing = self.distribution.data_files or []
        self.distribution.data_files = list(existing) + [("bin", bin_files)]

    def get_outputs(self, include_bytecode: bool = True):  # type: ignore[override]
        outputs = super().get_outputs(include_bytecode)
        outputs.extend(getattr(self, "_generated_outputs", []))
        return outputs


class BinaryDistribution(Distribution):
    """Mark wheel as non-pure so platform tag is kept."""

    def has_ext_modules(self) -> bool:
        return True

    def is_pure(self) -> bool:
        return False


long_description = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

setup(
    name="bison-bin",
    version=PACKAGE_VERSION,
    description="Prebuilt GNU Bison packaged as a Python wheel",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="GPL-3.0-or-later",
    license_files=["LICENSE"],
    python_requires=">=3.8",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    entry_points={},
    scripts=[],
    cmdclass={
        "build_py": BuildPyWithBison,
        "build_bison": build_bison,
    },
    distclass=BinaryDistribution,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
    ],
)

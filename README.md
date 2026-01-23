# bison-bin

Prebuilt GNU Bison shipped as a Python wheel. Intended for reproducible CI environments that need a known Bison version without touching system packages.

## Features
- Bundles the `bison` binary plus its runtime data under the Python package.
- Installs the raw `bison` (and `yacc`) executables into your environment `bin`—no Python wrapper.
- Manylinux x86_64/aarch64 and macOS x86_64/arm64 wheels via `cibuildwheel`.
- Builds Bison (and its m4 dependency) from upstream release tarballs; no system package installs.

## Installation
```
pip install bison-bin
```

## Usage
```
bison --help
bison --version
```
Optional from Python for discovery:
```python
from bison_bin import get_binary_path
print(get_binary_path())
```

## Configuration
Build-time environment variables:
- `BISON_VERSION`: desired Bison version (e.g., `3.8.2`). If unset, the build tries to discover the latest release from https://ftp.gnu.org/gnu/bison/ with a fallback to a pinned default.
- `M4_VERSION`: m4 version to build (default `1.4.19`).
- `BISON_BIN_VERSION`: Python package version to publish. Defaults to `BISON_VERSION`.
- `BISON_BUILD_PARALLEL`: `make -j` parallelism (default `4`).
- `BISON_BIN_STRIP`: if set to `1`, strip the installed binaries after build.

Runtime environment variables:
- `BISON_BIN_PATH`: override the resolved binary path for debugging.
- `BISON_BIN_ROOT`: override the packaged payload root (expected to contain `bin/bison`).

## Building locally
```
python -m pip install --upgrade pip
python -m pip install build
python -m build
```
Wheel artifacts will appear in `dist/`.

## Building wheels with cibuildwheel
```
python -m pip install cibuildwheel
python -m cibuildwheel --output-dir wheelhouse
```
Environment variables from the Configuration section are honored. Defaults target CPython 3.8–3.12 on Linux (x86_64, aarch64) and macOS (x86_64, arm64).

## Release workflow
- Tag the repo (e.g., `v3.8.2`).
- GitHub Actions builds platform wheels via `cibuildwheel` and publishes to PyPI when `PYPI_TOKEN` is present.

## License
GNU General Public License v3 or later. See `LICENSE`.

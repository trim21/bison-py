# bison-bin

Prebuilt GNU Bison shipped as a Python wheel.

## Features
- Bundles the full `make install` payload of Bison under the Python package.
- Provides `bison` and `yacc` entry points that exec the bundled binaries.
- Manylinux x86_64/aarch64 and macOS x86_64/arm64 wheels via `cibuildwheel`.
- Builds Bison from upstream release tarballs; no system package installs.

## Installation
```
pip install bison-bin
```

## Usage
```
bison --version
yacc --help
```

## Building locally
```
uv build --wheel .
```
Wheel artifacts will appear in `dist/`.

## License
GNU General Public License v3 or later. See `LICENSE`.

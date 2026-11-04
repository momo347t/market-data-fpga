#!/usr/bin/env python3
"""Install a pinned, hash-checked official OSS CAD Suite portable release."""
import argparse
import hashlib
from pathlib import Path
import platform
import tarfile
import urllib.request

RELEASE = "2026-11-03"
ASSETS = {
    "Linux": ("oss-cad-suite-linux-x64-20261103.tgz", "f991f2b5a8204028100cf3ad2d14d97c005ce14b903b50edf71399da99b417ed"),
    "Windows": ("oss-cad-suite-windows-x64-20261103.tgz", "69d06c135f6ae02488d8fb862d4884fbff0fde7b8af14ec10a6d7a910b060a4d"),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[2] / ".tools")
    args = parser.parse_args()
    if platform.machine().lower() not in ("amd64", "x86_64") or platform.system() not in ASSETS:
        parser.error("automatic installation supports Windows/Linux x86-64; see OSS CAD Suite for other platforms")
    destination = args.destination.resolve(); destination.mkdir(parents=True, exist_ok=True)
    version = destination / "oss-cad-suite" / "VERSION"
    if version.exists():
        if version.read_text().strip() == "20261103":
            print(destination / "oss-cad-suite"); return
        parser.error("a different toolchain already exists at the destination; choose another directory")
    filename, expected = ASSETS[platform.system()]
    archive = destination / filename
    if not archive.exists():
        url = f"https://github.com/YosysHQ/oss-cad-suite-build/releases/download/{RELEASE}/{filename}"
        print(f"Downloading official {filename}", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "market-data-fpga-tool-setup"})
        with urllib.request.urlopen(request, timeout=120) as source, archive.open("wb") as output:
            while chunk := source.read(1024*1024): output.write(chunk)
    digest = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
    if digest != expected: raise SystemExit("SHA-256 mismatch; archive was not extracted")
    with tarfile.open(archive, "r:gz") as bundle:
        bundle.extractall(destination, filter="data")
    if not version.exists() or version.read_text().strip() != "20261103":
        raise SystemExit("unexpected extracted toolchain version")
    print(destination / "oss-cad-suite")

if __name__ == "__main__": main()

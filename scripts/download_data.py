#!/usr/bin/env python3
"""Download and verify the official UCI SECOM source archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


DATASET_PAGE = "https://archive.ics.uci.edu/dataset/179/secom"
ARCHIVE_URL = "https://archive.ics.uci.edu/static/public/179/secom.zip"
DOI = "https://doi.org/10.24432/C54305"
REQUIRED_FILES = ("secom.data", "secom_labels.data", "secom.names")
EXPECTED_SHA256 = {
    "secom.zip": "eea568baf3c2229096d7d294cf0b096b5502bd96d92c0b80a65b84714059be8e",
    "secom.data": "20f0e7ee434f7dcbae0eea9ffff009a2b57f42d6b0dc9a5bd4f00782c0a3374c",
    "secom_labels.data": "126884cf453705c9e61a903fe906f0665a3b45ce3639e621edc5c93c89627e03",
    "secom.names": "6d91b0b46cdee03064ee3e3112f937c1b3f7fcd9933575794ec07974e6f1ea59",
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
ARCHIVE_PATH = RAW_DIR / "secom.zip"
MANIFEST_PATH = RAW_DIR / "source_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_expected_hash(path: Path, expected_name: str | None = None) -> None:
    name = expected_name or path.name
    actual = sha256(path)
    expected = EXPECTED_SHA256[name]
    if actual != expected:
        raise RuntimeError(
            f"SHA-256 mismatch for {name}: expected {expected}, got {actual}"
        )


def download_archive(force: bool = False) -> bool:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if ARCHIVE_PATH.exists() and not force:
        assert_expected_hash(ARCHIVE_PATH)
        return False

    partial_path = ARCHIVE_PATH.with_suffix(".zip.part")
    request = urllib.request.Request(
        ARCHIVE_URL,
        headers={"User-Agent": "secom-quality-analysis/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        with partial_path.open("wb") as output:
            shutil.copyfileobj(response, output)
    assert_expected_hash(partial_path, expected_name=ARCHIVE_PATH.name)
    partial_path.replace(ARCHIVE_PATH)
    return True


def extract_required_files() -> None:
    assert_expected_hash(ARCHIVE_PATH)
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        by_basename = {Path(name).name: name for name in archive.namelist()}
        missing = [name for name in REQUIRED_FILES if name not in by_basename]
        if missing:
            raise RuntimeError(f"Required files missing from archive: {missing}")

        for name in REQUIRED_FILES:
            target = RAW_DIR / name
            with archive.open(by_basename[name]) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            assert_expected_hash(target)


def write_manifest(downloaded: bool) -> None:
    prior_downloaded_at = None
    if MANIFEST_PATH.exists() and not downloaded:
        try:
            prior_downloaded_at = json.loads(
                MANIFEST_PATH.read_text(encoding="utf-8")
            ).get("downloaded_at_utc")
        except (json.JSONDecodeError, OSError):
            prior_downloaded_at = None

    files = {
        path.name: {
            "sha256": sha256(path),
            "expected_sha256": EXPECTED_SHA256[path.name],
            "matches_expected": True,
            "size_bytes": path.stat().st_size,
        }
        for path in [ARCHIVE_PATH, *(RAW_DIR / name for name in REQUIRED_FILES)]
    }
    manifest = {
        "dataset": "SECOM",
        "dataset_page": DATASET_PAGE,
        "archive_url": ARCHIVE_URL,
        "doi": DOI,
        "license": "CC BY 4.0",
        "downloaded_at_utc": (
            datetime.now(timezone.utc).isoformat()
            if downloaded
            else prior_downloaded_at
        ),
        "integrity_policy": (
            "Every archive and extracted file must match the pinned SHA-256 "
            "values in scripts/download_data.py."
        ),
        "files": files,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Download the source archive again even when it already exists.",
    )
    args = parser.parse_args()

    downloaded = download_archive(force=args.force)
    extract_required_files()
    write_manifest(downloaded=downloaded)

    action = "Downloaded and verified" if downloaded else "Verified existing"
    print(f"{action} SECOM data in: {RAW_DIR}")
    print(f"Archive SHA-256: {sha256(ARCHIVE_PATH)}")


if __name__ == "__main__":
    main()

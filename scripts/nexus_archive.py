"""Bounded archive checks for Nexus publishing. No platform credentials."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

MAX_ARCHIVE = 96 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024


def positive_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def valid_nexus_id(value):
    # v3 identifiers are opaque strings, not necessarily legacy numeric IDs.
    return positive_id(value) or (isinstance(value, str) and value != '0'
        and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', value) is not None)


def inspect_archive(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE:
        raise ValueError("Archive missing or larger than the spike's 96 MiB limit")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    total, files, seen, mod_files = 0, 0, set(), 0
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            name = item.filename
            parts = PurePosixPath(name).parts
            if not parts or name.startswith("/") or "\\" in name or ":" in name or any(p in (".", "..") for p in name.split("/") if p):
                raise ValueError("Unsafe archive path")
            if name.casefold() in seen or item.flag_bits & 1 or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Duplicate, encrypted or symbolic-link entry")
            seen.add(name.casefold())
            if item.is_dir():
                continue
            total += item.file_size
            files += 1
            mod_files += int(name.lower().endswith(".mod"))
            if total > MAX_EXPANDED or files > 10000:
                raise ValueError("Archive exceeds expanded size or entry limit")
        if not mod_files:
            raise ValueError("No FCS .mod file: payload completeness needs investigation")
        if archive.testzip() is not None:
            raise ValueError("Archive CRC validation failed")
    return {"filename": path.name, "sha256": digest, "bytes": path.stat().st_size, "files": files,
            "expanded_bytes": total, "completeness": "FCS file present; runtime/dependency validation still required"}



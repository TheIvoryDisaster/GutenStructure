"""Offline publishing plans only. Never authenticates, extracts or uploads."""
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


def load_registry(path):
    registry = json.loads(Path(path).read_text())
    if registry.get("schema_version") != 1 or registry.get("live_publishing_enabled") is not False:
        raise ValueError("This spike requires schema 1 and live publishing disabled")
    mods = registry.get("mods")
    if not isinstance(mods, dict) or not mods:
        raise ValueError("A nonempty mod registry is required")
    for name, target in mods.items():
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError("Invalid mod key")
        if target.get("repository") != "Meitou-Modding-Ecosystem/MeitouMods":
            raise ValueError("Repository is outside the spike allowlist")
        steam, nexus = target["steam"], target["nexus"]
        if steam.get("app_id") != 233860 or nexus.get("game") != "kenshi":
            raise ValueError("Only Kenshi is covered by this spike")
        for value in [steam.get("published_file_id"), nexus.get("mod_id")]:
            if value is not None and not positive_id(value):
                raise ValueError("Destination IDs must be positive; zero could create a duplicate item")
        if nexus.get("file_id") is not None and not valid_nexus_id(nexus["file_id"]):
            raise ValueError("Invalid Nexus v3 file identifier")
        if not isinstance(steam.get("validated_for_kenshi"), bool):
            raise ValueError("Kenshi validation must be explicitly recorded")
        author = target.get("author")
        if author is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", author):
            raise ValueError("Invalid author account name")
    return registry


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


def plan(registry, mod, version, archive=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}", version):
        raise ValueError("Invalid version")
    target = registry["mods"][mod]
    payload = inspect_archive(archive) if archive else None
    blockers = ["Live publishing is intentionally disabled in this spike", "Author credentials and environment approvals have not been verified"]
    if not target["author"]:
        blockers.append("Confirm the publishing author and their destination permissions")
    if payload is None:
        blockers.append("Supply the complete release ZIP and verify its runtime dependencies")
    steam = []
    if not target["steam"]["published_file_id"]:
        steam.append("Record an existing Workshop item ID; automatic creation is forbidden")
    if not target["steam"]["validated_for_kenshi"]:
        steam.append("Validate SteamCMD update, Steam Guard and subscriber installation for Kenshi")
    nexus = []
    if not target["nexus"]["mod_id"] or not target["nexus"]["file_id"]:
        nexus.append("Manually create Nexus mod page and first file, then record both IDs")
    return {"mode":"dry-run", "would_publish":False, "mod":mod, "version":version,
            "repository":target["repository"], "payload":payload, "blockers":blockers,
            "steam":{"target":target["steam"], "blockers":steam},
            "nexus":{"target":target["nexus"], "blockers":nexus}}


def workshop_vdf(target, content_folder, version):
    # This file is only a preview: no steamcmd execution and no credentials.
    if not positive_id(target["published_file_id"]) or target["app_id"] != 233860:
        raise ValueError("An existing Kenshi item ID is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}", version):
        raise ValueError("Invalid version")
    if not content_folder.startswith("/") or any(c in content_folder for c in '\n\r\t"\\'):
        raise ValueError("Use an absolute Linux staging folder without VDF control characters")
    return ('"workshopitem"\n{\n'
            f'  "appid" "233860"\n  "publishedfileid" "{target["published_file_id"]}"\n'
            f'  "contentfolder" "{content_folder}"\n  "changenote" "Release {version}"\n}}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="distribution/targets.json")
    parser.add_argument("--mod", required=True)
    parser.add_argument("--version", default="0.0.0-spike")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--vdf", type=Path)
    parser.add_argument("--content-folder")
    args = parser.parse_args()
    try:
        registry = load_registry(args.registry)
        result = plan(registry, args.mod, args.version, args.archive)
        if args.vdf:
            if not args.content_folder:
                raise ValueError("--vdf requires --content-folder")
            vdf = workshop_vdf(registry["mods"][args.mod]["steam"], args.content_folder, args.version)
            with args.vdf.open("x") as output:
                output.write(vdf)
        print(json.dumps(result, indent=2))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        parser.exit(2, f"Invalid publishing plan: {error}\n")


if __name__ == "__main__":
    main()

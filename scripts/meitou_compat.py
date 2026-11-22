"""Checks a mod repository against the Meitou releases it will meet (docs/meitou-compat.md).

Builds every mod (a top-level folder holding meitou.json and <Folder>/<Folder>.csproj), then runs tools/refcheck against the newest full
Meitou release, the newest nightly and the oldest release each mod's gameVersion admits, for each mod assembly and each locked framework
assembly. Checks that the newest full release is inside each gameVersion, and where it is above a cap and nothing broke, lifts the cap to the
next patch above it. Writes into --out:

- report.json: the results (read by the workflow and the tests);
- issue.md: the issue body when something needs a person, else absent;
- lift.md and lift/<path>: the cap-lift PR's body and changed manifests, when a cap can be lifted.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.framework_update import format_version, parse_version, satisfies

MEITOU = "https://github.com/VlcekM/MeitouClient"
FULL_TAG = re.compile(r"^v(\d+\.\d+\.\d+)$")
NIGHTLY_TAG = re.compile(r"^v(\d+\.\d+\.\d+)-nightly\.(\d{8})(?:\.(\d+))?$")
UPPER_BOUND = re.compile(r"<\s*(\d+\.\d+\.\d+)")
LOWER_BOUND = re.compile(r">=?\s*\d+\.\d+\.\d+")


@dataclass(frozen=True)
class Release:
    tag: str
    version: tuple[int, int, int]
    nightly: bool = False
    order: tuple = ()

    @property
    def label(self) -> str:
        return self.tag.removeprefix("v")


@dataclass
class Mod:
    folder: str
    manifest: Path
    game_version: str
    assemblies: list[Path] = field(default_factory=list)


@dataclass
class Check:
    target: str
    kind: str
    assembly: str
    missing: list[str]
    stamps: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.stamps


# region Releases

def parse_tags(tags: list[str]) -> tuple[list[Release], list[Release]]:
    """Full releases and nightlies, oldest first."""
    full, nightly = [], []
    for tag in tags:
        if match := FULL_TAG.match(tag):
            version = parse_version(match.group(1))
            full.append(Release(tag, version, False, (version,)))
        elif match := NIGHTLY_TAG.match(tag):
            version = parse_version(match.group(1))
            nightly.append(Release(tag, version, True, (version, match.group(2), int(match.group(3) or 1))))
    return sorted(full, key=lambda r: r.order), sorted(nightly, key=lambda r: r.order)


def remote_tags(url: str) -> list[str]:
    output = subprocess.run(["git", "ls-remote", "--tags", url], check=True, capture_output=True, text=True).stdout
    return [line.split("refs/tags/", 1)[1] for line in output.splitlines() if "refs/tags/" in line and not line.endswith("^{}")]


def targets(full: list[Release], nightly: list[Release], ranges: list[str]) -> list[tuple[str, Release]]:
    """(kind, release) to check: the newest full release, a newer nightly, and the oldest release each range with a floor admits."""
    chosen: list[tuple[str, Release]] = []
    if full:
        chosen.append(("release", full[-1]))
    if nightly and (not full or nightly[-1].version > full[-1].version):
        chosen.append(("nightly", nightly[-1]))
    for range_text in (r for r in ranges if LOWER_BOUND.search(r)):
        floor = next((r for r in full if satisfies(range_text, r.version)), None)
        if floor is not None and all(floor.tag != r.tag for _, r in chosen):
            chosen.append(("floor", floor))
    return chosen


def newest_admitted(full: list[Release], range_text: str) -> Release | None:
    return next((r for r in reversed(full) if satisfies(range_text, r.version)), None)


def download(release: Release, cache: Path) -> Path:
    """The release's Meitou*.dll and 0Harmony.dll, from its win-x64 zip, kept in the cache."""
    folder = cache / release.label
    if any(folder.glob("Meitou*.dll")):
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "meitou.zip"
    urllib.request.urlretrieve(f"{MEITOU}/releases/download/{release.tag}/Meitou-{release.label}-win-x64.zip", archive)
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            base = name.rsplit("/", 1)[-1]
            if base.endswith(".dll") and (base.startswith("Meitou") or base == "0Harmony.dll"):
                (folder / base).write_bytes(zipped.read(name))
    archive.unlink()
    if not any(folder.glob("Meitou*.dll")):
        raise ValueError(f"no Meitou*.dll in {release.tag}'s win-x64 zip")
    return folder

# endregion

# region The repository

def find_mods(root: Path) -> list[Mod]:
    mods = []
    for manifest in sorted(root.glob("*/meitou.json")):
        folder = manifest.parent.name
        if (manifest.parent / f"{folder}.csproj").exists():
            mods.append(Mod(folder, manifest, json.loads(manifest.read_text(encoding="utf-8")).get("gameVersion", "")))
    return mods


def build(root: Path, mod: Mod, out: Path) -> None:
    output = out / "build" / mod.folder
    project = root / mod.folder / f"{mod.folder}.csproj"
    subprocess.run(["dotnet", "build", str(project), "-c", "Release", "-o", str(output), "-v", "q", "-nologo"], check=True)
    names = json.loads(mod.manifest.read_text(encoding="utf-8")).get("assemblies", [])
    mod.assemblies = [output / name for name in names]


def framework_assemblies(root: Path) -> list[tuple[str, Path, str]]:
    """Each locked framework's assemblies (label, path, its own gameVersion), as the build extracted them into deps/<tag>/<folder>/."""
    lock = root / "meitou.lock.json"
    if not lock.exists():
        return []
    found = []
    for entry in json.loads(lock.read_text(encoding="utf-8")).get("frameworks", []):
        folder = root / "deps" / entry["tag"] / entry["folder"]
        manifest = json.loads((folder / "meitou.json").read_text(encoding="utf-8"))
        found += [(f"{entry['tag']}/{name}", folder / name, manifest.get("gameVersion", "")) for name in manifest.get("assemblies", [])]
    return found


def assemblies(mods: list[Mod], frameworks: list[tuple[str, Path, str]], release: Release) -> list[tuple[str, Path]]:
    """What to check against a release: each mod assembly unless the release is below the mod's floor (still checked above its cap, which
    a lift needs), and each framework assembly whose own gameVersion admits the release (one it refuses never loads beside the mod, and its
    own repository's watch reports it)."""
    mine = [(f"{m.folder}/{a.name}", a) for m in mods if not below_floor(m.game_version, release) for a in m.assemblies]
    return mine + [(label, path) for label, path, range_text in frameworks if satisfies(range_text, release.version)]

# endregion

# region Checks

def refcheck(tool: Path, assembly: Path, release_dir: Path) -> tuple[list[str], list[str]]:
    """RefCheck's MISSING and STAMP lines for one assembly against one release."""
    result = subprocess.run(["dotnet", str(tool), "check", str(assembly), str(release_dir)], capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"RefCheck failed on {assembly}: {result.stderr.strip()}")
    lines = result.stdout.splitlines()
    return ([l.removeprefix("MISSING ") for l in lines if l.startswith("MISSING ")],
            [l.removeprefix("STAMP ") for l in lines if l.startswith("STAMP ")])


def api_version(tool: Path, release_dir: Path) -> int | None:
    """The release's code-mod API version, or None when RefCheck can't read it."""
    result = subprocess.run(["dotnet", str(tool), "api", str(release_dir)], capture_output=True, text=True)
    return int(result.stdout.strip()) if result.returncode == 0 else None


def next_patch(version: tuple[int, int, int]) -> tuple[int, int, int]:
    return version[0], version[1], version[2] + 1


def lifted(range_text: str, release: Release) -> str | None:
    """The range with its cap moved to the next patch above a full release it excludes from above, else None."""
    match = UPPER_BOUND.search(range_text)
    if match is None or satisfies(range_text, release.version) or parse_version(match.group(1)) > release.version:
        return None
    widened = UPPER_BOUND.sub(f"<{format_version(next_patch(release.version))}", range_text, count=1)
    return widened if satisfies(widened, release.version) else None


def below_floor(range_text: str, release: Release) -> bool:
    """Whether the range's lower bound excludes the release: a mod built for a Meitou that has no full release yet."""
    floor = " ".join(LOWER_BOUND.findall(range_text))
    return bool(floor) and not satisfies(floor, release.version)


def decide(mods: list[Mod], checks: list[Check], newest: Release | None, apis: dict[str, int], admitted: dict[str, str | None]) -> dict:
    """What needs a person (issues) and which caps can move (lifts), from the checks; no I/O."""
    issues = [f"`{c.assembly}` against {c.target}: " + "; ".join([*(f"missing `{m}`" for m in c.missing), *(f"engine stamp {s}" for s in c.stamps)])
              for c in checks if not c.ok and c.kind != "nightly"]
    warnings = [f"`{c.assembly}` against {c.target}: " + "; ".join(f"missing `{m}`" for m in c.missing)
                for c in checks if c.kind == "nightly" and c.missing]
    lifts = {}
    if newest is not None:
        newest_clean = all(c.ok for c in checks if c.target == newest.tag)
        for mod in mods:
            if satisfies(mod.game_version, newest.version):
                continue
            if below_floor(mod.game_version, newest):
                warnings.append(f"`{mod.folder}` `gameVersion` `{mod.game_version}` starts above {newest.tag}, the newest full release: it "
                                "loads only in nightlies until that Meitou ships")
                continue
            widened = lifted(mod.game_version, newest)
            below = admitted.get(mod.folder)
            same_api = below is not None and apis.get(below) is not None and apis.get(below) == apis.get(newest.tag)
            if widened and newest_clean and same_api:
                lifts[mod.folder] = widened
                continue
            reason = ("RefCheck found a break" if not newest_clean else
                      f"its code-mod API changed ({apis.get(below)} → {apis.get(newest.tag)}): test it in play, then lift the cap by hand"
                      if widened and not same_api else "the range can't be lifted automatically")
            issues.append(f"`{mod.folder}` `gameVersion` `{mod.game_version}` excludes {newest.tag}: {reason}")
    return {"issues": issues, "warnings": warnings, "lifts": lifts}

# endregion

# region Output

def checks_table(checks: list[Check]) -> list[str]:
    rows = ["| Meitou | Checked as | Assembly | Result |", "| --- | --- | --- | --- |"]
    for c in checks:
        result = "ok" if c.ok else f"{len(c.missing)} missing, {len(c.stamps)} newer stamps"
        rows.append(f"| {c.target} | {c.kind} | `{c.assembly}` | {result} |")
    return rows


def write(out: Path, root: Path, mods: list[Mod], checks: list[Check], outcome: dict, newest: Release | None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    report = {**outcome, "checks": [c.__dict__ for c in checks], "newest": newest.tag if newest else None}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    table = checks_table(checks)
    if outcome["issues"] or outcome["warnings"]:
        body = ["The daily Meitou compatibility watch found something (docs/meitou-compat.md in GutenStructure)."]
        if outcome["issues"]:
            body += ["", *(f"- {line}" for line in outcome["issues"])]
        if outcome["warnings"]:
            body += ["", "Nightly only (a warning until a full release ships it):", "", *(f"- {line}" for line in outcome["warnings"])]
        body += ["", *table, "", "This issue closes itself once the watch passes again."]
        (out / "issue.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    if outcome["lifts"]:
        write_lift(out, root, mods, outcome["lifts"], newest, table)


def write_lift(out: Path, root: Path, mods: list[Mod], lifts: dict[str, str], newest: Release, table: list[str]) -> None:
    lines = [f"Meitou {newest.tag} is out and nothing this repository calls is missing from it, so each cap moves to just above it:", ""]
    for mod in (m for m in mods if m.folder in lifts):
        manifest = json.loads(mod.manifest.read_text(encoding="utf-8"))
        manifest["gameVersion"] = lifts[mod.folder]
        target = out / "lift" / mod.manifest.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        lines.append(f"- `{mod.folder}` `gameVersion` `{mod.game_version}` → `{lifts[mod.folder]}`")
    lines += ["", "**Needs a release:** players only get the wider range with a release of each mod (docs/versioning.md).", "", *table]
    (out / "lift.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# endregion


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--refcheck", type=Path, required=True, help="RefCheck.dll, built from tools/refcheck")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("/tmp/meitou-releases"))
    parser.add_argument("--tags", nargs="*", help="Meitou tags to choose from instead of the repository's")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    mods = find_mods(root)
    if not mods:
        print("no mods (a top-level folder with meitou.json and <Folder>/<Folder>.csproj): nothing to check")
        return 0
    for mod in mods:
        build(root, mod, args.out)
    frameworks = framework_assemblies(root)

    full, nightly = parse_tags(args.tags if args.tags is not None else remote_tags(MEITOU))
    newest = full[-1] if full else None
    chosen = targets(full, nightly, [m.game_version for m in mods])
    admitted = {m.folder: (r.tag if (r := newest_admitted(full, m.game_version)) else None) for m in mods}
    for tag in {t for t in admitted.values() if t} - {r.tag for _, r in chosen}:
        chosen.append(("admitted", next(r for r in full if r.tag == tag)))

    checks, apis, unchecked = [], {}, []
    for kind, release in chosen:
        try:
            folder = download(release, args.cache)
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            unchecked.append((kind, f"couldn't check {release.tag}: {error}"))
            continue
        apis[release.tag] = api_version(args.refcheck, folder)
        if kind == "admitted":
            continue
        for label, assembly in assemblies(mods, frameworks, release):
            missing, stamps = refcheck(args.refcheck, assembly, folder)
            checks.append(Check(release.tag, kind, label, missing, stamps))

    outcome = decide(mods, checks, newest, apis, admitted)
    outcome["warnings"] += [text for kind, text in unchecked if kind == "nightly"]
    outcome["issues"] += [text for kind, text in unchecked if kind != "nightly"]
    write(args.out, root, mods, checks, outcome, newest)
    print("\n".join(checks_table(checks)))
    return 1 if outcome["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

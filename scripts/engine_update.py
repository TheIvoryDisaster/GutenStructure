"""Keeps a mod repository's engine on the newest upstream Meitou build (docs/engine-update.md).

Without --engine: a repository with no frameworks in meitou.lock.json moves its `engine` submodule to the newest tag of VlcekM/MeitouClient,
nightly or full release, whichever is newer. A repository that locks frameworks follows their engine instead (framework-update), so this
does nothing there.

With --engine <sha> (framework-update, after it moved the engine to the lock's commit): only the floor below follows that commit's tag.

Either way the floor moves with the engine (docs/versioning.md): Directory.Build.rsp's `-p:AssemblyVersion=<X.Y.Z>.0` and each mod's
`gameVersion` lower bound become the tag's release X.Y.Z (a nightly counts as the release it leads to, as the game does), a cap at or below
the new floor goes, and a manifest whose version is already released moves to the next patch (scripts/release_bump.py).

Prints the new engine commit on stdout (empty when nothing moves) and writes the PR body to --summary.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.framework_update import GitHub, format_version, parse_version
from scripts.release_bump import bump

MEITOU = "https://github.com/VlcekM/MeitouClient"
TAG = re.compile(r"^v(\d+\.\d+\.\d+)(?:-nightly\.(\d{8})(?:\.(\d+))?)?$")
RSP_STAMP = re.compile(r"-p:AssemblyVersion=(\d+\.\d+\.\d+)\.0")
LOWER = re.compile(r">=?\s*(\d+\.\d+\.\d+)")
UPPER = re.compile(r"\s*<\s*(\d+\.\d+\.\d+)")


# region Tags

def order(tag: str) -> tuple | None:
    """Sort key for a Meitou tag: SemVer, so a nightly sorts below the release it leads to; None for any other tag."""
    match = TAG.match(tag)
    if match is None:
        return None
    nightly = match.group(2) is not None
    return parse_version(match.group(1)), 0 if nightly else 1, match.group(2) or "", int(match.group(3) or 1)


def release_of(tag: str) -> tuple[int, int, int]:
    return parse_version(TAG.match(tag).group(1))


def newest(tags: dict[str, str]) -> str | None:
    """The newest Meitou tag (nightly or full) among tag -> commit."""
    known = [tag for tag in tags if order(tag) is not None]
    return max(known, key=order, default=None)


def tag_of(tags: dict[str, str], commit: str) -> str | None:
    """The newest Meitou tag on a commit, or None when it carries none (a fork or development commit)."""
    on = [tag for tag, sha in tags.items() if sha == commit and order(tag) is not None]
    return max(on, key=order, default=None)


def remote_tags(url: str) -> dict[str, str]:
    """tag -> commit, peeled (an annotated tag's ^{} line wins)."""
    output = subprocess.run(["git", "ls-remote", "--tags", url], check=True, capture_output=True, text=True).stdout
    tags: dict[str, str] = {}
    for line in output.splitlines():
        sha, ref = line.split("\t", 1)
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            tags[name[:-3]] = sha
        else:
            tags.setdefault(name, sha)
    return tags

# endregion

# region The repository

def locks_frameworks(root: Path) -> bool:
    lock = root / "meitou.lock.json"
    return lock.exists() and bool(json.loads(lock.read_text(encoding="utf-8")).get("frameworks"))


def pinned(root: Path) -> str:
    """The engine commit the repository's HEAD records."""
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD:engine"], check=True, capture_output=True, text=True).stdout.strip()


def floored(range_text: str, floor: tuple[int, int, int]) -> str:
    """The range with its lower bound at the floor, and its cap dropped when the floor reaches it."""
    text = LOWER.sub(f">={format_version(floor)}", range_text, count=1) if LOWER.search(range_text) else \
        f">={format_version(floor)} {range_text}".strip()
    cap = UPPER.search(text)
    if cap and parse_version(cap.group(1)) <= floor:
        text = UPPER.sub("", text, count=1).strip()
    return text


def move_rsp(root: Path, floor: tuple[int, int, int], notes: list[str]) -> None:
    rsp = root / "Directory.Build.rsp"
    if not rsp.exists():
        notes.append("- No `Directory.Build.rsp`: the build stamps engine references `1.0.0.0`, which released games refuse; add one.")
        return
    text = rsp.read_text(encoding="utf-8")
    match = RSP_STAMP.search(text)
    stamp = f"-p:AssemblyVersion={format_version(floor)}.0"
    if match is None:
        rsp.write_text(text.rstrip("\n") + ("\n" if text.strip() else "") + stamp + "\n", encoding="utf-8")
    elif parse_version(match.group(1)) != floor:
        rsp.write_text(RSP_STAMP.sub(stamp, text, count=1), encoding="utf-8")
    else:
        return
    notes.append(f"- `Directory.Build.rsp`: `{match.group(0) if match else '(none)'}` → `{stamp}`")


def move_manifests(root: Path, floor: tuple[int, int, int], releases: list[dict], notes: list[str]) -> None:
    bumps: list[str] = []
    for manifest_path in sorted(root.glob("*/meitou.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        old = manifest.get("gameVersion")
        if old is None:
            notes.append(f"- `{manifest_path.parent.name}` has no `gameVersion`: it loads in any Meitou, including ones older than its engine.")
            continue
        new = floored(old, floor)
        if new == old:
            continue
        manifest["gameVersion"] = new
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        notes.append(f"- `{manifest_path.parent.name}` `gameVersion` `{old}` → `{new}`")
        bump(manifest_path, releases, bumps)
    if bumps:
        notes += ["", "Versions bumped so the release carries the change:", "", *bumps]


def move_floor(root: Path, tag: str, releases: list[dict], notes: list[str]) -> None:
    floor = release_of(tag)
    move_rsp(root, floor, notes)
    move_manifests(root, floor, releases, notes)


def own_releases() -> list[dict]:
    """The repository's GitHub releases, for the patch bump; none outside Actions."""
    repository = os.environ.get("GITHUB_REPOSITORY")
    return GitHub(os.environ.get("GITHUB_TOKEN")).releases(repository) if repository else []

# endregion


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--engine", help="Only move the floor to this engine commit's tag (framework-update)")
    parser.add_argument("--current", help="The engine commit now pinned (default: HEAD:engine)")
    parser.add_argument("--tags", type=Path, help="JSON tag -> commit instead of the upstream repository's tags (tests)")
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--tag-out", type=Path, help="Where to write the tag the engine moves to")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    tags = json.loads(args.tags.read_text(encoding="utf-8")) if args.tags else remote_tags(MEITOU)
    notes: list[str] = []

    if args.engine:
        tag = tag_of(tags, args.engine)
        if tag is None:
            print(f"engine {args.engine[:7]} carries no Meitou tag: the floor stays", file=sys.stderr)
            return 0
        move_floor(root, tag, own_releases(), notes)
        if args.summary and notes:
            args.summary.write_text("\n".join([f"The floor follows the engine to Meitou {tag}:", "", *notes]) + "\n", encoding="utf-8")
        return 0

    if locks_frameworks(root):
        print("frameworks are locked: the engine follows them (framework-update)", file=sys.stderr)
        return 0
    target = newest(tags)
    if target is None:
        return 0
    current = args.current or pinned(root)
    current_tag = tag_of(tags, current)
    if tags[target] == current or (current_tag and order(current_tag) >= order(target)):
        print(f"engine is on {current_tag or current[:7]}, the newest upstream build", file=sys.stderr)
        return 0
    notes.append(f"- `engine`: `{current_tag or current[:7]}` → `{target}` (`{tags[target][:7]}`)")
    move_floor(root, target, own_releases(), notes)
    if args.summary:
        body = [f"Moves the engine to {target}, the newest upstream Meitou build, with the floor that goes with it (GutenStructure "
                "docs/engine-update.md):", "", *notes, "",
                "**Needs a release** for players to get the new floor. A red CI here means the new Meitou broke something: port it in this PR "
                "(skill `meitou-engine-release`)."]
        args.summary.write_text("\n".join(body) + "\n", encoding="utf-8")
    if args.tag_out:
        args.tag_out.write_text(target + "\n", encoding="utf-8")
    print(tags[target])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

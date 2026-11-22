"""Moves a Meitou mod repository's meitou.lock.json to the newest published framework releases (docs/framework-update.md).

Run from the repository root. For each locked framework it finds the newest immutable release on the chosen channel, verifies the asset's
SHA-256 against the release notes, and rewrites the lock entry. With --widen-ranges, a mod manifest whose dependency range excludes the
new version gets its upper bound raised to the next breaking version, so the build and tests decide. Writes a Markdown summary and prints
the new engine commit (empty when unchanged).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API = "https://api.github.com"
RELEASE_TAG = re.compile(r"^(?P<slug>.+)-v(?P<version>\d+\.\d+\.\d+)$")
BETA_TAG = re.compile(r"^(?P<slug>.+)-(?P<version>\d+\.\d+\.\d+)-beta\.(?P<commit>[0-9a-f]{7,40})$")
ENGINE_NOTE = re.compile(r"Submodule engine at ([0-9a-f]{40})")
SHA_NOTE = re.compile(r"Zip SHA-256: `([0-9a-f]{64})`")
UPPER_BOUND = re.compile(r"<\s*(\d+\.\d+\.\d+)")
COMPARATOR = re.compile(r"(>=|<=|>|<|=)?\s*(\d+\.\d+\.\d+)")


@dataclass(frozen=True)
class Candidate:
    """
    One immutable framework release a lock may pin.
    """

    tag: str
    version: tuple[int, int, int]
    published: str
    body: str
    assets: tuple[dict, ...]


def parse_version(text: str) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in text.split("."))
    return major, minor, patch


def format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def slug_of(tag: str) -> str:
    match = RELEASE_TAG.match(tag) or BETA_TAG.match(tag)
    if match is None:
        raise ValueError(f"lock tag {tag!r} is not an immutable release tag (<slug>-v<version> or <slug>-<version>-beta.<commit>)")
    return match.group("slug")


def version_of(tag: str) -> tuple[int, int, int]:
    match = RELEASE_TAG.match(tag) or BETA_TAG.match(tag)
    if match is None:
        raise ValueError(f"not a release tag: {tag!r}")
    return parse_version(match.group("version"))


def candidates(releases: list[dict], slug: str, channel: str) -> list[Candidate]:
    """
    The releases of one framework a lock on this channel may pin: production releases, plus beta snapshots on the beta channel.
    The rolling <slug>-beta tag never matches.
    """
    found = []
    for release in releases:
        if release.get("draft"):
            continue
        tag = release["tag_name"]
        match = RELEASE_TAG.match(tag)
        if match is None and channel == "beta":
            match = BETA_TAG.match(tag)
        if match is None or match.group("slug") != slug:
            continue
        found.append(Candidate(tag, parse_version(match.group("version")), release.get("published_at") or "", release.get("body") or "",
                               tuple(release.get("assets") or ())))
    return found


def newest(found: list[Candidate], channel: str) -> Candidate | None:
    """
    Release channel: the highest version. Beta channel: the most recently published build of the highest version, since beta snapshots
    of one version follow each other.
    """
    if not found:
        return None
    top = max(candidate.version for candidate in found)
    same = [candidate for candidate in found if candidate.version == top]
    if channel == "release":
        return same[0]
    return max(same, key=lambda candidate: candidate.published)


def is_newer(candidate: Candidate, current_tag: str, current_published: str) -> bool:
    if candidate.tag == current_tag:
        return False
    current = version_of(current_tag)
    if candidate.version != current:
        return candidate.version > current
    return candidate.published > current_published


def zip_asset(candidate: Candidate, folder: str) -> dict:
    """
    The release's mod zip: <folder>-<version>.zip on a release, the one versioned zip on a beta snapshot.
    """
    zips = [asset for asset in candidate.assets if asset["name"].endswith(".zip") and asset["name"].startswith(folder)]
    zips = [asset for asset in zips if not asset["name"].endswith("-beta.zip")]
    if len(zips) != 1:
        names = [asset["name"] for asset in candidate.assets]
        raise ValueError(f"{candidate.tag}: expected one {folder}*.zip asset, found {names}")
    return zips[0]


def satisfies(range_text: str, version: tuple[int, int, int]) -> bool:
    for operator, bound_text in COMPARATOR.findall(range_text):
        bound = parse_version(bound_text)
        if operator == ">=" and not version >= bound:
            return False
        if operator == ">" and not version > bound:
            return False
        if operator == "<=" and not version <= bound:
            return False
        if operator == "<" and not version < bound:
            return False
        if operator in ("", "=") and version != bound:
            return False
    return True


def next_breaking(version: tuple[int, int, int]) -> tuple[int, int, int]:
    major, minor, _ = version
    return (0, minor + 1, 0) if major == 0 else (major + 1, 0, 0)


def widen(range_text: str, version: tuple[int, int, int]) -> str | None:
    """
    The range with its upper bound raised to admit the version (below the next breaking version), or None when the range can't be widened
    that way (no upper bound, or its lower bound excludes the version).
    """
    if satisfies(range_text, version) or UPPER_BOUND.search(range_text) is None:
        return None
    widened = UPPER_BOUND.sub(f"<{format_version(next_breaking(version))}", range_text, count=1)
    return widened if satisfies(widened, version) else None


class GitHub:
    """
    Reads public releases with the job's read-only token.
    """

    def __init__(self, token: str | None) -> None:
        self._token = token

    def _request(self, url: str, accept: str) -> urllib.request.Request:
        request = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "meitou-framework-update"})
        if self._token:
            request.add_header("Authorization", f"Bearer {self._token}")
        return request

    def releases(self, repo: str) -> list[dict]:
        with urllib.request.urlopen(self._request(f"{API}/repos/{repo}/releases?per_page=100", "application/vnd.github+json")) as response:
            return json.load(response)

    def sha256(self, url: str) -> str:
        digest = hashlib.sha256()
        with urllib.request.urlopen(self._request(url, "application/octet-stream")) as response:
            for chunk in iter(lambda: response.read(1 << 16), b""):
                digest.update(chunk)
        return digest.hexdigest()


def update_entry(entry: dict, github: GitHub, channel: str, notes: list[str]) -> Candidate | None:
    """
    Moves one lock entry to its framework's newest release; returns that release, or None when the entry is current.
    """
    releases = github.releases(entry["repo"])
    current = next((release for release in releases if release["tag_name"] == entry["tag"]), None)
    current_published = current.get("published_at", "") if current else ""
    candidate = newest(candidates(releases, slug_of(entry["tag"]), channel), channel)
    if candidate is None or not is_newer(candidate, entry["tag"], current_published):
        return None

    asset = zip_asset(candidate, entry["folder"])
    engine = ENGINE_NOTE.search(candidate.body)
    if engine is None:
        raise ValueError(f"{candidate.tag}: release notes name no engine commit ('Submodule engine at <sha>')")
    sha256 = github.sha256(asset["browser_download_url"])
    noted = SHA_NOTE.search(candidate.body)
    if noted is not None and noted.group(1) != sha256:
        raise ValueError(f"{candidate.tag}: {asset['name']} hashes to {sha256}, release notes say {noted.group(1)}")

    notes.append(f"- `{entry['id']}`: `{entry['tag']}` → `{candidate.tag}` (engine `{engine.group(1)[:7]}`)")
    entry.update(tag=candidate.tag, asset=asset["name"], sha256=sha256, engine=engine.group(1))
    return candidate


def widen_manifests(root: Path, versions: dict[str, tuple[int, int, int]], notes: list[str]) -> None:
    for manifest_path in sorted(root.glob("*/meitou.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        changed = False
        for dependency in manifest.get("dependencies") or []:
            version = versions.get(dependency.get("id"))
            widened = widen(dependency.get("version", ""), version) if version else None
            if widened is None:
                continue
            notes.append(f"- `{manifest.get('id')}` accepts `{dependency['id']}` `{dependency['version']}` → `{widened}`")
            dependency["version"] = widened
            changed = True
        if changed:
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", choices=("release", "beta"), default="release")
    parser.add_argument("--widen-ranges", action="store_true")
    parser.add_argument("--summary", default="framework-update.md")
    args = parser.parse_args(argv)

    root = Path.cwd()
    lock_path = root / "meitou.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    github = GitHub(os.environ.get("GITHUB_TOKEN"))

    notes: list[str] = []
    moved = {entry["id"]: update_entry(entry, github, args.channel, notes) for entry in lock.get("frameworks", [])}
    moved = {framework: candidate for framework, candidate in moved.items() if candidate is not None}
    if not moved:
        print("")
        return 0

    engines = {entry["engine"] for entry in lock["frameworks"]}
    if len(engines) != 1:
        raise ValueError(f"the newest releases name different engine commits {sorted(engines)}; move the chain's frameworks together")
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

    manifest_notes: list[str] = []
    if args.widen_ranges:
        widen_manifests(root, {framework: candidate.version for framework, candidate in moved.items()}, manifest_notes)

    summary = ["Moves `meitou.lock.json` to the newest published framework releases.", "", *notes]
    if manifest_notes:
        summary += ["", "Dependency ranges widened so the new versions are accepted (the tests decide):", "", *manifest_notes]
        summary += ["", "**Needs a release:** players' installed copies still carry the old range, and the loader refuses a mod whose dependency "
                    "is out of range, optional ones too (docs/versioning.md)."]
    Path(args.summary).write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(engines.pop())
    return 0


if __name__ == "__main__":
    sys.exit(main())

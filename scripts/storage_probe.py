"""Verify one tiny blob round-trip and deny access to another project container."""
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

ACCOUNT = "gutenhub"
CONTAINER = "meitouclient-debug"
DENIED_CONTAINER = "gutendisplay-debug"


def az(*args, expected_denial=False):
    result = subprocess.run(["az", "storage", "blob", *args,
                             "--account-name", ACCOUNT, "--auth-mode", "login",
                             "--only-show-errors", "--output", "none"],
                            capture_output=True, text=True, timeout=90)
    if expected_denial:
        if result.returncode == 0:
            raise RuntimeError("Isolation failed: the probe could list another project's container")
        if "AuthorizationPermissionMismatch" not in result.stderr:
            raise RuntimeError("Negative check failed for a reason other than an RBAC permission denial")
        return
    if result.returncode:
        raise RuntimeError(f"Azure blob {args[0]} failed; review the identity's scope and data-plane connectivity")


def main():
    run, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    if not run.isdigit() or not attempt.isdigit():
        raise ValueError("Expected numeric GitHub run identifiers")
    name = f"gutenstructure-probe/{run}/{attempt}/probe.txt"
    created = False
    with tempfile.TemporaryDirectory() as directory:
        source, downloaded = Path(directory) / "source.txt", Path(directory) / "downloaded.txt"
        source.write_text("GutenStructure storage isolation probe\n" + os.environ["GITHUB_SHA"] + "\n")
        try:
            az("upload", "--container-name", CONTAINER, "--name", name,
               "--file", str(source), "--overwrite", "false")
            created = True
            az("download", "--container-name", CONTAINER, "--name", name,
               "--file", str(downloaded), "--overwrite", "true")
            if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(downloaded.read_bytes()).digest():
                raise RuntimeError("Downloaded content differs from uploaded content")
            print("PASS: upload, read-back and SHA-256 equality")
            az("list", "--container-name", DENIED_CONTAINER, "--num-results", "1", expected_denial=True)
            print("PASS: cross-container listing denied by RBAC")
        finally:
            if created:
                az("delete", "--container-name", CONTAINER, "--name", name)
                print("PASS: temporary probe blob removed")


if __name__ == "__main__":
    main()

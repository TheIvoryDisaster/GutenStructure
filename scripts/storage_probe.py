"""Verify one tiny blob round-trip and deny access to another project container."""
import hashlib
import os
import subprocess
import tempfile
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from email.utils import formatdate
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
            # The storage CLI rewrites Azure's error code into prose. Inspect the raw
            # protocol status/code so a network failure cannot masquerade as RBAC denial.
            token = subprocess.check_output(["az", "account", "get-access-token", "--resource",
                "https://storage.azure.com/", "--query", "accessToken", "--output", "tsv"], text=True).strip()
            request = urllib.request.Request(
                f"https://{ACCOUNT}.blob.core.windows.net/{DENIED_CONTAINER}?restype=container&comp=list&maxresults=1",
                headers={"Authorization": "Bearer " + token, "x-ms-version": "2023-11-03",
                         "x-ms-date": formatdate(usegmt=True)})
            try:
                with urllib.request.urlopen(request, timeout=30):
                    raise RuntimeError("Isolation failed: another project container was accessible")
            except urllib.error.HTTPError as error:
                code = ET.fromstring(error.read(4096)).findtext("Code")
                if error.code != 403 or code != "AuthorizationPermissionMismatch":
                    raise RuntimeError("Negative check did not return the expected RBAC denial") from None
            print("PASS: cross-container listing denied by RBAC")
        finally:
            if created:
                az("delete", "--container-name", CONTAINER, "--name", name)
                print("PASS: temporary probe blob removed")


if __name__ == "__main__":
    main()

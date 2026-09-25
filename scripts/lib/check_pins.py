#!/usr/bin/env python3
"""Every third-party `uses:` must be a full 40-character commit SHA.

A floating tag is mutable: the owner can repoint it at any commit, so a
pinned version comment is the only record of what a SHA was meant to be.
References to this repo's own actions are exempt - they are versioned by
this repo's own history.
"""
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SELF = "atkaridarshan04/shared-ci-actions"

USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)")
SHA = re.compile(r"^[0-9a-f]{40}$")
VERSION_COMMENT = re.compile(r"#\s*v?\d+\.\d+")


def main():
    failed = False
    files = sorted(
        list((REPO_ROOT / ".github").rglob("*.yml"))
        + list((REPO_ROOT / ".github").rglob("*.yaml"))
        + list((REPO_ROOT / "pipelines" / "templates").glob("*.tmpl"))
    )

    for path in files:
        for lineno, line in enumerate(path.read_text().split("\n"), 1):
            match = USES.match(line)
            if not match:
                continue
            ref = match.group(1)
            rel = path.relative_to(REPO_ROOT)

            if ref.startswith("./") or ref.startswith(SELF):
                continue  # local path, or this repo's own action

            if "@" not in ref:
                print(f"    {rel}:{lineno}: no ref at all: {ref}")
                failed = True
                continue

            pin = ref.rsplit("@", 1)[1]
            if not SHA.match(pin):
                print(f"    {rel}:{lineno}: floating ref '@{pin}' - use a full commit SHA")
                failed = True
            elif not VERSION_COMMENT.search(line):
                print(f"    {rel}:{lineno}: SHA-pinned but missing the '# vX.Y.Z' comment")
                failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

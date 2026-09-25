#!/usr/bin/env python3
"""Render every repo x stage combination, parse it, and reject leaked placeholders.

A leaked `{{NAME}}` is valid YAML and fails only at runtime, so parsing alone
does not catch it. The lookbehind avoids matching GitHub's own `${{ }}`.
"""
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "lib" / "pipeline_lib.py"
STAGES = ("dev", "qa")
PLACEHOLDER = re.compile(r"(?<!\$)\{\{[A-Z_]+\}\}")


def main():
    doc = yaml.safe_load((REPO_ROOT / "pipelines" / "repos.yaml").read_text()) or {}
    repos = doc.get("repos") or {}
    if not repos:
        print("    pipelines/repos.yaml has no `repos:` entries")
        return 1
    failed = False

    for repo in repos:
        for stage in STAGES:
            label = f"{repo}/{stage}"
            result = subprocess.run(
                [sys.executable, str(LIB), "render", repo, stage],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                print(f"    {label}: render failed\n{result.stderr}")
                failed = True
                continue

            try:
                doc = yaml.safe_load(result.stdout)
            except yaml.YAMLError as exc:
                print(f"    {label}: rendered output is not valid YAML: {exc}")
                failed = True
                continue

            if not doc or "jobs" not in doc:
                print(f"    {label}: rendered workflow has no jobs")
                failed = True
                continue

            leaks = PLACEHOLDER.findall(result.stdout)
            if leaks:
                print(f"    {label}: unrendered placeholders {sorted(set(leaks))}")
                failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

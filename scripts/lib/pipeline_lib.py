#!/usr/bin/env python3
"""Template rendering for scripts/install-pipeline.sh.

Not meant to be run standalone except via its subcommands
(render / filename).
"""
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "pipelines" / "repos.yaml"
TEMPLATES_DIR = REPO_ROOT / "pipelines" / "templates"

STAGE_FILES = {
    "dev": ("dev-pipeline.yml.tmpl", "dev-pipeline.yml"),
    "qa": ("qa-release.yml.tmpl", "qa-release.yml"),
}

# indentation of a `with:` key inside a step, in the templates
WITH_INDENT = " " * 10

# placeholders that carry their own indentation and expand to zero or more
# whole lines. Every other placeholder is substituted inline, keeping the
# template's indentation - so these must be listed, not detected by shape.
BLOCK_PLACEHOLDERS = {"EXTRA_BUILD_INPUTS"}


def load_config(repo):
    all_config = yaml.safe_load(CONFIG_PATH.read_text())
    if repo not in all_config:
        print(
            f"No config entry for '{repo}' in pipelines/repos.yaml - "
            "add one first (see the file's header comment).",
            file=sys.stderr,
        )
        sys.exit(1)
    return all_config[repo]


def extra_build_inputs(config):
    """Render the optional build-candidate-image inputs, or nothing.

    Emitting `build-args: |` with an empty block below it is valid YAML but
    pointless noise, so both inputs are dropped entirely when unset.
    """
    lines = []

    target = (config.get("dockerfile_target") or "").strip()
    if target:
        lines.append(f"{WITH_INDENT}dockerfile-target: {target}")

    build_args = [
        line.strip()
        for line in str(config.get("build_args") or "").split("\n")
        if line.strip()
    ]
    if build_args:
        lines.append(f"{WITH_INDENT}build-args: |")
        lines.extend(f"{WITH_INDENT}  {arg}" for arg in build_args)

    return "\n".join(lines)


def render(template_text, config):
    values = {
        "SERVICE_NAME": config["service_name"],
        "SERVICE_LABEL": config["service_label"],
        "HELM_KEY": config["helm_key"],
        "SEMGREP_CONFIGS": config.get("semgrep_configs", ""),
        "EXTRA_BUILD_INPUTS": extra_build_inputs(config),
    }

    out_lines = []
    for line in template_text.split("\n"):
        stripped = line.strip()
        if stripped[2:-2] in BLOCK_PLACEHOLDERS and stripped.startswith("{{"):
            block = values[stripped[2:-2]]
            if block:  # renders to nothing -> drop the line entirely
                out_lines.append(block)
            continue
        for key, val in values.items():
            line = line.replace("{{%s}}" % key, val)
        out_lines.append(line)
    return "\n".join(out_lines)


def cmd_render(repo, stage):
    config = load_config(repo)
    tmpl_name, _ = STAGE_FILES[stage]
    print(render((TEMPLATES_DIR / tmpl_name).read_text(), config), end="")


def cmd_filename(stage):
    print(STAGE_FILES[stage][1])


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"render", "filename"}:
        print("usage: pipeline_lib.py <render <repo> <stage>|filename <stage>>", file=sys.stderr)
        sys.exit(2)

    if sys.argv[1] == "render":
        cmd_render(sys.argv[2], sys.argv[3])
    else:
        cmd_filename(sys.argv[2])


if __name__ == "__main__":
    main()

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

REQUIRED_DEFAULTS = ("integration_branch", "helm_repo", "runner", "actions_ref")

# indentation of a `with:` key inside a step, in the templates
WITH_INDENT = " " * 10

# placeholders that carry their own indentation and expand to zero or more
# whole lines. Every other placeholder is substituted inline, keeping the
# template's indentation - so these must be listed, not detected by shape.
BLOCK_PLACEHOLDERS = {"EXTRA_BUILD_INPUTS"}


def load_config(repo):
    """Return one repo's config, with `defaults` merged in underneath it."""
    doc = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    defaults = doc.get("defaults") or {}
    repos = doc.get("repos") or {}

    missing = [k for k in REQUIRED_DEFAULTS if k not in defaults]
    if missing:
        print(
            f"pipelines/repos.yaml is missing required defaults: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    if repo not in repos:
        print(
            f"No config entry for '{repo}' in pipelines/repos.yaml - "
            "add one first (see the file's header comment).",
            file=sys.stderr,
        )
        sys.exit(1)

    # per-repo keys win over defaults
    return {**defaults, **repos[repo]}


def load_default(key):
    doc = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return (doc.get("defaults") or {}).get(key)


def list_repos():
    doc = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return list((doc.get("repos") or {}))


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
    helm_repo = config["helm_repo"]
    if "/" not in helm_repo:
        print(
            f"helm_repo must be \"owner/name\", got '{helm_repo}'",
            file=sys.stderr,
        )
        sys.exit(1)
    helm_owner, helm_repo_name = helm_repo.split("/", 1)

    values = {
        "SERVICE_NAME": config["service_name"],
        "SERVICE_LABEL": config["service_label"],
        "HELM_KEY": config["helm_key"],
        "SEMGREP_CONFIGS": config.get("semgrep_configs", ""),
        "INTEGRATION_BRANCH": config["integration_branch"],
        "ACTIONS_REF": config["actions_ref"],
        "RUNNER": config["runner"],
        "HELM_REPO": helm_repo,
        "HELM_OWNER": helm_owner,
        "HELM_REPO_NAME": helm_repo_name,
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


def cmd_default(key):
    value = load_default(key)
    if value is None:
        print(f"No default '{key}' in pipelines/repos.yaml", file=sys.stderr)
        sys.exit(1)
    print(value)


def cmd_config(repo, key):
    value = load_config(repo).get(key)
    if value is None:
        print(f"No '{key}' for '{repo}' in pipelines/repos.yaml", file=sys.stderr)
        sys.exit(1)
    print(value)


def main():
    commands = {"render", "filename", "config", "default", "list-repos"}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(
            "usage: pipeline_lib.py <render <repo> <stage>|filename <stage>|"
            "config <repo> <key>|default <key>|list-repos>",
            file=sys.stderr,
        )
        sys.exit(2)

    cmd = sys.argv[1]
    if cmd == "render":
        cmd_render(sys.argv[2], sys.argv[3])
    elif cmd == "filename":
        cmd_filename(sys.argv[2])
    elif cmd == "config":
        cmd_config(sys.argv[2], sys.argv[3])
    elif cmd == "default":
        cmd_default(sys.argv[2])
    else:
        print("\n".join(list_repos()))


if __name__ == "__main__":
    main()

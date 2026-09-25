# Scripts

`scripts/install-pipeline.sh` installs one pipeline-stage file into one repo,
by opening a PR on that repo. It is the only script here; everything else is
declarative config under `pipelines/`.

## Prerequisites

- `gh auth login`, under an account with push access to the target repo. The
  script runs as you — there is no stored credential.
- `PyYAML` (`pip install pyyaml`) for the templating step.

## Usage

```
scripts/install-pipeline.sh <repo-name> <dev|qa> [--force]
```

| | |
|---|---|
| `repo-name` | must have an entry in `pipelines/repos.yaml` |
| stage | `dev` or `qa` |
| `--force` | replace the stage file if the repo already has one |

Environment overrides:

| Variable | Default | Meaning |
|---|---|---|
| `GITHUB_OWNER` | `atkaridarshan04` | account that owns the target repo |
| `BASE_BRANCH` | `develop` | branch to clone, and the PR's base |

```
scripts/install-pipeline.sh test-api dev
GITHUB_OWNER=someone-else scripts/install-pipeline.sh test-web qa
```

## What it does

1. Renders `pipelines/templates/<stage>.yml.tmpl` against the repo's entry in
   `pipelines/repos.yaml` — **before cloning anything**, so a bad or missing
   config fails with no side effects.
2. Clones the target repo at `BASE_BRANCH`, shallow.
3. Refuses to overwrite an existing stage file unless `--force`.
4. Writes `.github/workflows/<stage>.yml`, parses it to confirm it's valid
   YAML, commits it on a `ci/add-<stage>-pipeline` branch, and opens a PR.

## Why it refuses unknown repos

The script will not run against a repo with no entry in
`pipelines/repos.yaml`. Build args, Semgrep configs, and the values-file key
cannot be inferred by pattern-matching against other repos — a guessed entry
ships a broken pipeline into a real repo, not just a bad doc. Read the target
repo's Dockerfile and existing CI, then add the entry.

## Adding a repo

See the header comment in [`pipelines/repos.yaml`](../pipelines/repos.yaml)
for the field list. Minimum viable entry:

```yaml
my-service:
  service_name: api
  service_label: api
  helm_key: .services.api.imageTag
  semgrep_configs: "p/python p/dockerfile p/secrets"
```

`dockerfile_target` and `build_args` are optional — omit them and the
corresponding action inputs are left out of the rendered file entirely.

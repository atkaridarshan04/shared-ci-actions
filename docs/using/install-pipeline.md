# Installing a pipeline into a repo

`scripts/install-pipeline.sh` renders a stage template against a repo's entry
in `pipelines/repos.yaml` and opens a PR adding it. One repo and one stage at
a time — deliberately not a bulk operation.

Prerequisites: `PyYAML` (`pip install pyyaml`), and `gh auth login` under an
account with push access to the target repo. The script runs as you; there is
no stored credential.

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

## Configuration

[`pipelines/repos.yaml`](../../pipelines/repos.yaml) has two sections.
`defaults` applies to every repo; `repos` holds one entry each. Any repo may
override any default.

```yaml
defaults:
  integration_branch: develop
  helm_repo: atkaridarshan04/test-helm-charts
  runner: ubuntu-latest

repos:
  my-service:
    service_name: api
    service_label: api
    helm_key: .services.api.imageTag
    semgrep_configs: "p/python p/dockerfile p/secrets"
```

### Per-repo fields

| Field | Required | Meaning |
|---|---|---|
| `service_name` | yes | image tag suffix, `component-name`, `component-label` |
| `service_label` | yes | human label in the Trivy comment header |
| `helm_key` | yes | yq path into the charts repo's values file |
| `semgrep_configs` | yes | space-separated packs, matched to the repo's stack |
| `dockerfile_target` | no | `--target` stage; omitted entirely when unset |
| `build_args` | no | newline-separated `KEY=VALUE`; omitted entirely when unset |

### Defaults, overridable per repo

| Field | Default | Drives |
|---|---|---|
| `integration_branch` | `develop` | both dev triggers, QA's PR base, and `base-branch` on `promote-candidate-image` |
| `helm_repo` | — | `helm-repo`, plus the App token's `owner` / `repositories` scoping |
| `runner` | `ubuntu-latest` | `runs-on` for every job |

`integration_branch` is deliberately one setting driving four places. They
must agree: if the pipeline triggers on `main` but `promote-candidate-image`
looks for PRs against `develop`, every merge fails with "nothing scanned to
promote."

```yaml
repos:
  legacy-service:
    integration_branch: main      # this repo never adopted develop
    runner: self-hosted
    service_name: api
    ...
```

## What isn't configurable

Deliberately fixed in the templates. Change these by editing
[`pipelines/templates/`](../../pipelines/templates) directly:

| | Why |
|---|---|
| Registry (`ghcr.io`) | Changing it means changing the login step, job permissions, and credential — not just a string. A setting here would half-work and fail confusingly. |
| Release branch pattern (`release-*`) | Convention; changing it is rare enough not to earn permanent API surface. |
| Values paths (`dev/values.yaml`, `qa/values.yaml`) | Same. |

## What the repo needs before the pipeline will pass

- a `develop` branch (the integration branch both stages assume)
- a `Dockerfile` the build step can use
- the Helm-charts repo entry named by `helm_key`, and the App credentials
  from [`github-app-setup.md`](github-app-setup.md)

The scan gates are blocking by default. See
[`security-scanning.md`](security-scanning.md) before the first PR, so a red
run isn't a surprise.

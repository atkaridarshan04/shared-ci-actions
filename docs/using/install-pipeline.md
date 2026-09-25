# Installing a pipeline into a repo

`scripts/install-pipeline.sh` renders a stage template against a repo's config
and opens a PR adding it. One repo, one stage at a time — not a bulk
operation.

Needs `PyYAML` and `gh auth login` under an account with push access to the
target. It runs as you; there's no stored credential.

```
scripts/install-pipeline.sh <repo-name> <dev|qa> [--force]
```

| | |
|---|---|
| `repo-name` | must have an entry in `pipelines/repos.yaml` |
| stage | `dev` or `qa` |
| `--force` | replace the stage file if one already exists |

| Env override | Default |
|---|---|
| `GITHUB_OWNER` | `atkaridarshan04` |
| `BASE_BRANCH` | the repo's `integration_branch` |

```
scripts/install-pipeline.sh test-api dev
GITHUB_OWNER=someone-else scripts/install-pipeline.sh test-web qa
```

It renders **before cloning anything**, so a bad config fails with no side
effects; clones shallow; refuses to overwrite without `--force`; then parses
the result as YAML before committing it to a `ci/add-<stage>-pipeline` branch
and opening a PR.

It won't run against a repo with no config entry. Build args, Semgrep configs,
and the values key can't be inferred by pattern-matching other repos — a
guessed entry ships a broken pipeline into a real repo.

## Configuration

[`pipelines/repos.yaml`](../../pipelines/repos.yaml): `defaults` applies to
every repo, `repos` holds one entry each, any repo can override any default.

```yaml
defaults:
  integration_branch: develop
  helm_repo: atkaridarshan04/test-helm-charts
  runner: ubuntu-latest
  actions_ref: main

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
| `service_label` | yes | label in the Trivy comment header |
| `helm_key` | yes | yq path into the charts repo's values file |
| `semgrep_configs` | yes | space-separated packs, matched to the stack |
| `dockerfile_target` | no | `--target` stage; omitted entirely when unset |
| `build_args` | no | newline-separated `KEY=VALUE`; omitted when unset |

### Defaults

| Field | Default | Drives |
|---|---|---|
| `integration_branch` | `develop` | both dev triggers, QA's PR base, `base-branch` on `promote-candidate-image` |
| `helm_repo` | — | `helm-repo`, plus the App token's `owner`/`repositories` |
| `runner` | `ubuntu-latest` | `runs-on` for every job |
| `actions_ref` | `main` | which version of *this* repo pipelines call |

`integration_branch` is one setting driving four places **because they must
agree** — trigger on `main` while `promote-candidate-image` looks for PRs
against `develop` and every merge fails with "nothing scanned to promote".

`actions_ref` stays `main` until the first release, meaning every commit here
reaches consumers immediately. Set it to `v1` after releasing — see
[versioning](../maintaining/versioning.md).

```yaml
repos:
  legacy-service:
    integration_branch: main      # never adopted develop
    runner: self-hosted
    actions_ref: v1.2.3           # pinned while it stabilises
    service_name: api
```

### Not configurable

Fixed in the templates — edit
[`pipelines/templates/`](../../pipelines/templates) to change them:

| | Why |
|---|---|
| Registry (`ghcr.io`) | Changing registries means changing the login step, permissions, and credential. A string knob would half-work and fail confusingly. |
| Release pattern (`release-*`) | Convention; too rare to earn permanent API surface. |
| Values paths (`dev/`, `qa/values.yaml`) | Same. |

## Before the first run

The target repo needs its integration branch and a `Dockerfile`; the charts
repo needs the key named by `helm_key`; and the App credentials from
[github-app-setup](github-app-setup.md) must exist.

Scan gates block by default — read
[security-scanning](security-scanning.md) first so a red PR isn't a surprise.

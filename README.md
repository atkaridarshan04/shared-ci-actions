# shared-ci-actions

[![CI](https://github.com/atkaridarshan04/shared-ci-actions/actions/workflows/ci.yml/badge.svg)](https://github.com/atkaridarshan04/shared-ci-actions/actions/workflows/ci.yml)

Reusable GitHub Actions building blocks for a two-stage container pipeline —
**dev** and **QA** — plus the tooling to roll it out to app repos without
copy-pasting it into each one.

**Build once. Scan before push. Promote by digest.** No image is ever rebuilt
between "scanned" and "deployed."

---

## Quick start

Images go to GHCR using `GITHUB_TOKEN` — no registry account, no cloud
credentials. The charts repo is the only real setup.

```bash
# 1. add your repo to pipelines/repos.yaml (copy test-api and edit)
# 2. install the dev pipeline — opens a PR on that repo
./scripts/install-pipeline.sh <repo-name> dev
```

Before that works, the app repo needs a `develop` branch and a `Dockerfile`,
and you need a charts repo plus the App credentials from
[`github-app-setup.md`](docs/using/github-app-setup.md).

Run `./scripts/verify.sh` before pushing changes here — it's exactly what CI runs.

---

## The two stages

| File | Trigger | What it does |
|:--|:--|:--|
| `dev-pipeline.yml` | PR + push to `develop` | Semgrep → build → Trivy → PR comments. On merge: promote by digest, commit `dev/values.yaml` |
| `qa-release.yml` | push to `release-*` | Build → Trivy → push, then open a PR bumping `qa/values.yaml` |

Deploy config lives in a **separate Helm-charts repo**, so the pipeline never
commits to the branch that triggered it.

---

## Layout

```
.github/
  actions/        composite actions — the building blocks
  workflows/      CI, fleet automation, release tagging
docs/
  using/          adopting these pipelines in an app repo
  maintaining/    changing this repo
pipelines/        templates + per-repo config
scripts/          verify this repo; install a pipeline into another
```

---

## Docs

**Using** — adopting these pipelines

| | |
|:--|:--|
| [dev-pipeline](docs/using/dev-pipeline.md) | Build once, promote by digest. Tagging, failure modes |
| [qa-release](docs/using/qa-release.md) | Release branches, and why QA lands through a PR |
| [security-scanning](docs/using/security-scanning.md) | **When a scan blocks your PR** — suppression mechanics + policy |
| [install-pipeline](docs/using/install-pipeline.md) | Installing a stage, and the full config reference |
| [github-app-setup](docs/using/github-app-setup.md) | Required cross-repo charts credential |

**Maintaining** — changing this repo

| | |
|:--|:--|
| [workflows](docs/maintaining/workflows.md) | The workflows that run *here* |
| [verifying](docs/maintaining/verifying.md) | `verify.sh` — what it covers, what it doesn't |
| [versioning](docs/maintaining/versioning.md) | Releases, `@v1`, Dependabot, pin maintenance |

---

## Configuration

[`pipelines/repos.yaml`](pipelines/repos.yaml) — `defaults` applies to every
repo, `repos` holds one entry each, and any repo can override any default.

```yaml
defaults:
  integration_branch: develop        # triggers, PR base, promote's base-branch
  helm_repo: owner/charts-repo       # also scopes the App token
  runner: ubuntu-latest

repos:
  my-service:
    service_name: api
    helm_key: .services.api.imageTag
    semgrep_configs: "p/python p/dockerfile p/secrets"
```

Registry, release-branch pattern, and values paths are deliberately **not**
configurable — see [install-pipeline](docs/using/install-pipeline.md#what-isnt-configurable)
for why.

---

## Conventions

- Third-party `uses:` are pinned to full commit SHAs, and `verify.sh`
  **enforces** it rather than trusting the convention.
- Composite actions, not `workflow_call` — callers keep control of their
  triggers, permissions, and job structure.
- [`CLAUDE.md`](CLAUDE.md) has the full set.

> [!NOTE]
> Templates currently reference `@main`, so every commit here reaches
> consumers immediately. Once you cut `v1`, switch them to `@v1` — see
> [versioning](docs/maintaining/versioning.md).

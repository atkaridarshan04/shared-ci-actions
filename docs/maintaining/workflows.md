# Workflows in this repo

These run *here*. The pipelines installed into app repos are a different
thing — see [`docs/using/`](../using/dev-pipeline.md).

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | PR, push to `main` | Verification suite + actionlint |
| `release.yml` | manual | Cut `vX.Y.Z`, move the `vX` tag |
| `fleet-branch.yml` | manual | Create a branch across many repos |
| `prod-release.yml` | manual | Promote one release tag into prod values |

## `ci.yml`

Runs [`verify.sh`](../../scripts/verify.sh) — the same command you run
locally — plus `actionlint`, which catches invalid `${{ }}` expressions and
bad `needs:` references that a YAML parse accepts, and shellchecks every
`run:` block. See [verifying](verifying.md).

## `release.yml`

Cuts an immutable `vX.Y.Z` tag and force-moves `vX` to it. Refuses to reuse a
version tag, requires a bare `X.Y.Z`, runs `verify.sh` first, and refuses to
cut a major while `actions_ref` still names the previous one.

See [versioning](versioning.md) for what counts as breaking, and why that last
check is a guard rather than an automatic rewrite.

## `fleet-branch.yml`

One branch across many repos. A release cut is `from_branch: develop`; a
hotfix cut is `from_branch: release-x.y.z` — the same operation, which is why
it's one workflow.

- **Git refs API, not a clone per repo** — one request, nothing to clean up.
- **One matrix job per repo, `fail-fast: false`** — a single loop meant repo 3
  of 13 failing left repos 4–13 unrun with no record of what happened. Each
  repo now succeeds or fails independently and writes a summary row.
- **`dry_run: true` by default** — resolves every source branch and reports
  what it would create.

Re-running is safe: a repo that already has the branch is skipped, not failed.

## `prod-release.yml`

Sets every service's `imageTag` in the prod values file to one release tag and
opens a PR. The service list is newline-separated yq paths in the workflow's
`env:` — add a line to onboard a service.

Two bugs it fixes from the version it replaced:

- **Verifies each path exists before writing.** `yq` happily creates a key no
  chart reads, so a typo produced a PR that changed nothing.
- **Can run twice.** The original checked for its branch with `git rev-parse`
  against a shallow clone, so the check never matched and a re-run failed on
  push.

`dry_run: true` by default, printing the diff and stopping.

## Deliberately not carried over

Two workflows were dropped rather than genericized.

**`custom-deployment`** cloned app repos, regex-rewrote their workflow files,
and force-pushed without a PR.
[`install-pipeline.sh`](../../scripts/install-pipeline.sh) already does that
job properly — renders from a template, validates it parses, opens a PR.

**`automated-env`** provisioned an environment by copying a rendered chart
directory and running ~190 lines of `sed` over it. That's templating
implemented as regex, in a stack already running Helm. Every environment
became a duplicated directory that drifts permanently, and patterns like
`s/nonprod/${ENV}/g` rewrote that string anywhere it appeared. The
replacement isn't a workflow — it's `values-<env>.yaml` against one chart.

## Credentials

`fleet-branch` and `prod-release` use `secrets.AUTOMATION_PAT`, not the GitHub
App the pipelines use. The App is installed on the charts repo only — which is
the point of it — while these need write access across many repos.

Removing the PAT means either a second App installed on the app repos, or
narrowing these until `GITHUB_TOKEN` suffices. Both are real work; don't swap
the credential without picking one.

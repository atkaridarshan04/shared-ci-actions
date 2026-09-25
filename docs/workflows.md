# Workflows in this repo

These run *here*, on this repo. They are not the pipelines installed into app
repos — those are [`pipelines/templates/`](../pipelines/templates), documented
in [`dev-pipeline.md`](dev-pipeline.md) and [`qa-release.md`](qa-release.md).

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | PR, push to `main` | Verification suite + actionlint |
| `release.yml` | manual | Cut `vX.Y.Z`, move the `vX` tag |
| `fleet-branch.yml` | manual | Create a branch across many repos |
| `prod-release.yml` | manual | Promote one release tag into prod values |

## `ci.yml`

Runs [`scripts/verify.sh`](../scripts/verify.sh) — the same command you run
locally — plus `actionlint`, which catches invalid `${{ }}` expressions and
bad `needs:` references that a plain YAML parse accepts, and runs shellcheck
over every `run:` block.

This repo's product *is* YAML and bash, so this is the only thing between a
typo and a broken pipeline in every consumer repo.

## `release.yml`

Cuts an immutable `vX.Y.Z` tag and force-moves the `vX` tag to it, so
consumers can reference `@v1` and receive fixes without receiving breaking
changes — the scheme `actions/checkout` and friends use.

It refuses to reuse an existing version tag, requires a bare `X.Y.Z` (no
leading `v`, no prerelease suffix), and runs `verify.sh` before tagging so a
release can't be cut from a broken tree.

> The templates currently reference this repo at `@main`, which means every
> commit here reaches every consumer immediately. Once you cut `v1`, change
> the `@main` refs in `pipelines/templates/*.tmpl` to `@v1`.

## `fleet-branch.yml`

Creates one branch across many repos. Replaces the old `release-branch` +
`hotfix-release` pair, which were the same operation differing only in source
branch — a release cut is `from_branch: develop`, a hotfix cut is
`from_branch: release-x.y.z`.

Three things it does that the originals didn't:

- **Uses the Git refs API**, not a clone per repo. One request, nothing to
  clean up, no `git` subprocess handling.
- **Runs one matrix job per repo with `fail-fast: false`.** The originals
  looped inside a single job, so repo 3 of 13 failing meant repos 4–13 never
  ran and nothing recorded what had happened. Now each repo succeeds or fails
  independently and writes a row to the job summary.
- **Defaults to `dry_run: true`.** Resolves every source branch and reports
  what it would create, without creating it.

Re-running is safe: a repo that already has the branch is reported and
skipped, not failed.

## `prod-release.yml`

Sets every service's `imageTag` in the prod values file to one release tag and
opens a PR against the prod charts repo.

The service list is a newline-separated set of yq paths in the workflow's
`env:` block — add a line to onboard a service. The original hardcoded
thirteen separate `yq` calls.

It also fixes two real bugs from that version:

- **It verifies each path exists before writing.** `yq` happily creates a key
  that no chart reads, so a typo used to produce a silently ineffective PR.
- **It can run twice.** The original assumed its branch was new; a shallow
  clone meant the "does this branch exist" check never matched, so a re-run
  after a fixup failed on push. This force-pushes with lease and reuses an
  open PR.

Defaults to `dry_run: true`, which prints the resulting diff and stops.

## Deliberately not carried over

Two workflows from the internal setup were dropped rather than genericized.

**`custom-deployment`** cloned app repos, copied `dev-deploy.yaml` to
`deploy-<env>.yaml`, regex-rewrote the values path and trigger blocks, and
force-pushed — no PR. [`install-pipeline.sh`](../scripts/install-pipeline.sh)
already does that job properly: it renders from a template, validates the
result parses, and opens a PR. Keeping both would mean maintaining the worse
one.

**`automated-env`** provisioned a new environment by copying a rendered chart
directory and running ~190 lines of `sed` over it — rewriting namespaces,
hostnames, secret keys, and env vars by pattern. That is templating,
implemented as regex, in a stack that already runs Helm. Two problems made it
not worth porting:

- Every environment became a *duplicated directory*, so each one drifts from
  the source permanently. N environments means N copies to keep in sync by
  hand.
- The patterns matched more than they meant to. `s/nonprod/${ENV}/g` rewrites
  that string anywhere it appears, not only in the fields intended.

The replacement isn't a workflow — it's modelling environments as Helm values
(`values-<env>.yaml`) against one chart, which is what the chart is for. If a
one-click env bootstrap is still wanted later, it should generate a values
file, not a directory tree.

## A note on credentials

`fleet-branch` and `prod-release` use `secrets.AUTOMATION_PAT`, not the
GitHub App the pipelines use. That's deliberate: the App is installed on the
charts repo only, which is the point of it, while these two need write access
across many repos.

If you want to remove the PAT, the options are a second App installed on the
app repos, or narrowing these workflows until `GITHUB_TOKEN` suffices. Both
are real work — don't swap the credential without deciding which.

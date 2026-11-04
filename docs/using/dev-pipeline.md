# Dev pipeline (`dev-pipeline.yml`)

PR into `develop` → scan → build → merge → rebuild + rescan → deploy.

The step-level logic lives **once**, as the composite actions in
[`.github/actions/`](../../.github/actions/README.md). The pipeline *shape*
itself also lives once, as the
[`dev-pipeline.yml` reusable workflow](../../.github/workflows/dev-pipeline.yml):
every app repo's `dev-pipeline.yml` is a thin trigger block plus one `uses:`
job calling it, rendered from
[the template](../../pipelines/templates/dev-pipeline.yml.tmpl). The
alternative — one file copy-pasted into fifteen repos — drifts: a gate gets
quietly disabled in one, a fix lands in three, nobody knows which are current.

## Build on the PR, rebuild and rescan on merge

The PR build only checks that the image builds and scans clean; nothing is
pushed. Merging to `develop` rebuilds and rescans from scratch under the
release tag, and that build pushes. The alternative — pushing a PR image and
retagging it by digest on merge — relies on resolving which PR produced a
merge commit, which silently breaks under squash/rebase merges, and never
re-validates the bits actually reaching the registry. One extra build+scan per
merge buys both fixes.

`build-candidate-image` never pushes. The push job runs build → scan → login →
push, so a failing Trivy gate blocks the registry.

## Flow

```mermaid
flowchart TD
    subgraph PR["Pull request → develop"]
        A[Open / update PR] --> B["semgrep-scan-and-comment<br/>blocking"]
        A --> B2["gitleaks-scan<br/>blocking"]
        A --> B3["trivy-scan-and-comment<br/>scan-type: fs"]
        B --> C["build-candidate-image<br/>pr-&lt;number&gt;-&lt;service&gt;<br/>local only"]
        B2 --> C
        B3 --> C
        C --> D["trivy-scan-and-comment<br/>HIGH/CRITICAL, fixable<br/>blocking"]
    end

    D --> M{push to develop}
    M --> F1["build-candidate-image<br/>&lt;sha&gt;-&lt;service&gt;<br/>REBUILD"]
    F1 --> F2["trivy-scan-and-comment<br/>re-scan, artifact-name: trivy-reports-release"]
    F2 --> F3["docker login + push"]
    F3 --> G["update-helm-chart<br/>bump dev/values.yaml in charts repo"]
```

## Actions, in order

The build waits for the three PR scans to pass. A PR never pushes an image.

| Step | Action | Notes |
|---|---|---|
| SAST | `semgrep-scan-and-comment` | baseline packs plus the stack's extras |
| Secrets | `gitleaks-scan` | PR only, always blocks |
| Dependencies | `trivy-scan-and-comment` | PR only, `scan-type: fs` |
| Build | `build-candidate-image` | local tag, not pushed |
| Container scan | `trivy-scan-and-comment` | blocking by default — this is the gate |
| Rebuild | `build-candidate-image` + `trivy-scan-and-comment` (again) | `push` only; rebuilds and rescans, then pushes, rather than promoting a PR image by digest |
| Values bump | `update-helm-chart` | direct commit to the charts repo |

`validate-branch-jira` exists but is opt-in — no template wires it in.

## Tags

| Tag | Format | Notes |
|---|---|---|
| PR build | `pr-<number>-<service>` | local tag, never pushed |
| Release | `<commit-sha>-<service>` | the commit that landed on `develop`; what gets deployed |

## What a direct push to `develop` does

The push job has no dependency on a PR having existed at all — it just
rebuilds and rescans whatever is on `develop` after the push. A direct push
(bypassing a PR) still gets built, Trivy-scanned, and deployed if it passes;
it just never went through the source scans or a PR comment, since
they are `pull_request`-only. That's a real gap for a repo that wants SAST enforced on
every change reaching `develop` — branch protection requiring the PR workflow
is what closes it, not this pipeline.

## Registry

GHCR at `ghcr.io/${{ github.repository }}`, pushed with `GITHUB_TOKEN` and
`packages: write` — nothing to provision.

- **GHCR paths must be lowercase.** If your owner or repo name has uppercase
  letters, set `IMAGE_NAME` explicitly in the workflow's `env:`.
- **The first push creates a private package.** Fine for the pipeline itself;
  anything pulling from outside the repo needs its access widened once.

## Charts repo

`update-helm-chart` commits to a separate charts repo, so `GITHUB_TOKEN` can't
be used — the job mints a GitHub App token per run
([setup](github-app-setup.md), required).

Every app repo pushes to the same branch there, so concurrent merges race. The
action fetches, resets to the latest remote state, re-applies its one-key
edit, and retries — re-applying rather than rebasing, so a concurrent bump to
a different service can't conflict.

## Configuration

Per-repo and fleet-wide settings live in
[`pipelines/repos.yaml`](../../pipelines/repos.yaml) — see
[install-pipeline](install-pipeline.md). `develop` appears throughout this doc
but comes from `integration_branch` and is configurable.

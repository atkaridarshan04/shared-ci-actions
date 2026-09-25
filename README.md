# shared-ci-actions

Reusable GitHub Actions building blocks for a two-stage container pipeline —
dev and QA — plus the templates and tooling to roll that pipeline out to app
repos without copy-pasting it into each one.

Build once on the PR, scan before anything is pushed, then promote the *same
digest* on merge. No image is ever rebuilt between "scanned" and "deployed".

```
shared-ci-actions/
├── .github/
│   ├── actions/      composite actions — the dev/QA building blocks
│   └── workflows/    CI for this repo, plus fleet/release automations
├── docs/             pipeline design rationale + setup guides
├── pipelines/        templates + per-repo config for each app repo's pipeline
├── scripts/          installs a rendered pipeline into one repo, via a PR
├── CLAUDE.md         editing conventions — read before changing an action
└── README.md         this file
```

## What's here

**[`.github/actions/`](.github/actions/README.md)** — seven composite
actions: Semgrep scan, Trivy scan, build, promote-by-digest, values update,
PR resolution, and an opt-in Jira branch gate. Each README section shows the
`with:` block to copy.

**[`pipelines/`](pipelines/repos.yaml)** — the three stage templates and one
config entry per app repo (service name, Semgrep configs, build args, values
key). Templates are rendered, not copied.

**[`scripts/`](scripts/)** — `verify.sh` runs every check CI runs, with no
arguments; `install-pipeline.sh` renders a stage template for one repo and
opens a PR adding it. See [`docs/scripts.md`](docs/scripts.md).

**[`docs/`](docs/)** — why the pipelines are shaped this way:
[`dev-pipeline.md`](docs/dev-pipeline.md) (PR → `develop`, build once /
promote by digest), [`qa-release.md`](docs/qa-release.md) (release branches,
and why QA lands through a PR), [`github-app-setup.md`](docs/github-app-setup.md)
(required one-time setup for the cross-repo charts credential).

**[`.github/workflows/`](.github/workflows/)** — this repo's own CI plus two
fleet automations (`fleet-branch`, `prod-release`) and a release tagger. These
run *here*, not in app repos. See [`docs/workflows.md`](docs/workflows.md).

## The two stages

| File | Trigger | What it does |
|---|---|---|
| `dev-pipeline.yml` | PR + push to `develop` | Semgrep, build, Trivy, PR comments; on merge promotes by digest and commits `dev/values.yaml` in the charts repo |
| `qa-release.yml` | push to `release-*` | Build, Trivy, push; opens a PR bumping `qa/values.yaml` in the charts repo |

Deploy config lives in a separate Helm-charts repo, not in the app repo — so
the pipeline never commits into the branch that triggered it.

## Trying it on a repo

Images go to GHCR (`ghcr.io/<owner>/<repo>`) using `secrets.GITHUB_TOKEN` —
no registry account and no cloud credentials to provision. The charts repo is
the one thing that does need setup.

1. Create a Helm-charts repo (`test-helm-charts` in the templates) with a
   `develop` branch and a `dev/values.yaml` holding the key named by your
   entry's `helm_key`.
2. Follow [`docs/github-app-setup.md`](docs/github-app-setup.md) to create the
   App and set `HELM_BOT_APP_ID` / `HELM_BOT_APP_PRIVATE_KEY` on the app repo.
   Without this the values-update job cannot authenticate.
3. Add an entry for your app repo to
   [`pipelines/repos.yaml`](pipelines/repos.yaml) (copy `test-api` or
   `test-web` and edit).
4. Make sure the app repo has a `develop` branch and a `Dockerfile`, then
   install the dev stage:

   ```
   scripts/install-pipeline.sh <repo-name> dev
   ```

5. Merge that PR, then open a normal PR into `develop` and watch the scan
   comments land. On merge, check that the promoted tag appears in the charts
   repo's `dev/values.yaml`.

Add `qa` the same way once dev looks right. QA additionally needs a matching
`release-*` branch to exist in the charts repo.

## Conventions

Every third-party `uses:` is pinned to a full commit SHA with a version
comment — never a floating tag — and `scripts/verify.sh` enforces it rather
than trusting the convention. These are composite actions, deliberately, not
`workflow_call` reusable workflows: callers keep full control of their
triggers, permissions, and job structure, and these just inline as ordinary
steps. [`CLAUDE.md`](CLAUDE.md) has the full set.

Run `./scripts/verify.sh` before pushing. CI runs the same script, plus
`actionlint`.

## Versioning

Consumers reference these actions by ref, so a commit on `main` reaches every
consumer immediately. `release.yml` cuts an immutable `vX.Y.Z` tag and moves a
`vX` tag to it, the scheme `actions/checkout` uses.

The templates currently point at `@main`. **Once you cut `v1`, switch the refs
in `pipelines/templates/*.tmpl` to `@v1`** — until then there is no pinned ref
to point at.

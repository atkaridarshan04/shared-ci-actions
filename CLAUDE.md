# CLAUDE.md

See `README.md` for what's in this repo and where. This file is scoped to
editing conventions only.

## Conventions to apply on every edit

- **Composite actions only** — `.github/actions/*/action.yml` with
  `runs: using: composite`, never a `workflow_call` reusable workflow. This
  was a deliberate choice: callers stay in full control of triggers,
  permissions, and job structure; these actions just inline as ordinary
  steps. Don't introduce `on: workflow_call` here.
- **Pin every third-party `uses:` to a full commit SHA with a `# vX.Y.Z`
  comment** — never a floating tag (`@v3`), never `@master`/`@main`. Resolve
  the SHA with `gh api repos/<owner>/<repo>/commits/<tag> --jq .sha`. This
  applies to `.github/workflows/` too, not just the actions.
- **Keep the actions registry-agnostic.** They must only assume the calling
  job has already logged in. The templates happen to target GHCR; don't push
  registry-specific logic (ECR login, CodeArtifact secrets, `aws-actions/*`)
  down into an action.
- **`build-candidate-image` must never push.** The build → scan → login →
  push order is the security property the whole design rests on: an image
  that fails its Trivy gate must never reach the registry.
- **Deploy values live in a separate charts repo.** `update-helm-chart` takes
  a required `helm-repo` and a cross-repo token; don't reintroduce a default
  that points at the calling repo. Writing deploy config back into the app
  repo makes the pipeline commit to the branch that triggers it, which needs
  loop guards that this design avoids having to get right.
- An input that's pure internal plumbing (a scratch filename nothing outside
  the action reads) doesn't need to be caller-supplied — hardcode it, as
  `semgrep-scan-and-comment` and `trivy-scan-and-comment` already do for
  their report/comment files. Only expose an input when a caller genuinely
  needs to vary it.
- **Never add a `pipelines/repos.yaml` entry from pattern-matching other
  repos.** Read that repo's actual Dockerfile and existing pipeline first and
  copy its real build-args and Semgrep configs — `install-pipeline.sh` opens
  a PR against a real repo, so a guessed entry ships a broken pipeline, not
  just a bad doc.
- **Templates use two placeholder kinds.** Inline (`{{SERVICE_NAME}}`) keeps
  the template's indentation; block (`{{EXTRA_BUILD_INPUTS}}`, listed in
  `BLOCK_PLACEHOLDERS`) carries its own indentation and vanishes entirely
  when empty. A new block placeholder must be added to that set — otherwise
  it's substituted inline and its indentation is lost.

## Verifying a change

Run `./scripts/verify.sh` — it is exactly what CI runs: YAML syntax over
every action and workflow, every template rendered and parsed with a
placeholder-leak check, and a SHA-pin check on every third-party `uses:`.
Install `shellcheck` locally and it lints the scripts too; CI always does.

`actionlint` runs in CI on top of that and catches what a YAML parse cannot —
invalid `${{ }}` expressions, bad `needs:` references, a key used in a context
that doesn't provide it — plus shellcheck over every `run:` block.

What none of that covers is behaviour. Dry-run any new shell or Python logic
outside GitHub Actions: extract the `run:` string via `yaml.safe_load` (which
also proves what the block-scalar indentation actually collapses to), manually
substitute any `${{ github.* }}` expressions it references (bash chokes on the
literal `${{ }}` otherwise — a test-harness artifact, not a real bug), stub out
`curl`/`gh`/network calls, and execute with `bash`.

When you add a check to `verify.sh`, confirm it fails on bad input before
trusting it. A check that cannot go red is worse than no check — it reads as
coverage that isn't there.

## Gotchas worth keeping in mind

- **Empty arrays under `set -u`.** `"${ARR[@]}"` with `ARR=()` is an
  unbound-variable error on bash < 4.4 — which GitHub's ubuntu runners aren't,
  but a self-hosted runner may well be. Use `${ARR[@]+"${ARR[@]}"}`.
- **Never interpolate `${{ inputs.* }}` into a `run:` or `script:` body.**
  It is substituted before the shell ever starts, so a dispatch input can
  inject commands. Route it through `env:` and reference `"$VAR"`. Every
  workflow here does this; keep it that way.
- **Dependabot does not see `pipelines/templates/*.tmpl`.** It updates pins in
  `.github/workflows/` and composite `action.yml` files only, so template pins
  must be bumped by hand. `verify.sh` enforces that they stay SHA-pinned, but
  nothing tells you they've gone stale.
- **Consumers reference this repo by ref.** Changing an action on `main`
  changes every consumer immediately. Cut a release (`release.yml`) rather
  than relying on that.

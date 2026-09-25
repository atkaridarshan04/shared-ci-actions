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

## Verifying a changed action

There's no CI here that exercises these actions in isolation. Before calling
a change done:

```
python3 -c "import yaml; yaml.safe_load(open('PATH/action.yml'))"
```

for syntax, then dry-run any new shell+Python logic outside GitHub Actions:
extract the `run:` string via that same `yaml.safe_load` (this also proves
what the block-scalar indentation actually collapses to), manually
substitute any `${{ github.* }}` expressions it references (bash chokes on
the literal `${{ }}` otherwise — that's a test-harness artifact, not a real
bug), stub out `curl`/network calls, and execute with `bash`.

Watch for empty-array expansion under `set -u`: `"${ARR[@]}"` with `ARR=()`
is an unbound-variable error on bash < 4.4, which GitHub's ubuntu runners
aren't but a self-hosted runner may well be. Use `${ARR[@]+"${ARR[@]}"}`.

## Verifying a changed template

Render every repo × stage combination and parse each one:

```
for repo in $(python3 -c "import yaml;print(' '.join(yaml.safe_load(open('pipelines/repos.yaml'))))"); do
  for stage in dev qa; do
    python3 scripts/lib/pipeline_lib.py render "$repo" "$stage" \
      | python3 -c "import sys,yaml; yaml.safe_load(sys.stdin)" \
      && echo "OK $repo/$stage" || echo "FAIL $repo/$stage"
  done
done
```

Parsing alone doesn't catch a leaked placeholder — `{{SERVICE_NAME}}` is
valid YAML and fails only at runtime. Check for one in Python, not with
grep: a bare `{{` also matches GitHub's own `${{ }}` expressions, and some
greps (ugrep) reject `{{` as a malformed repeat quantifier.

```
python3 - <<'EOF'
import re, subprocess, yaml
pat = re.compile(r'(?<!\$)\{\{[A-Z_]+\}\}')   # not preceded by '$'
for repo in yaml.safe_load(open('pipelines/repos.yaml')):
    for stage in ('dev', 'qa'):
        out = subprocess.run(['python3', 'scripts/lib/pipeline_lib.py', 'render', repo, stage],
                             capture_output=True, text=True, check=True).stdout
        print(repo, stage, pat.findall(out) or 'clean')
EOF
```

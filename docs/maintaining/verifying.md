# Verifying a change

```
./scripts/verify.sh
```

No arguments, runnable from anywhere. This is exactly what CI runs — if it
passes locally, CI's `verify` job passes.

| Check | What it catches |
|---|---|
| YAML syntax | a malformed action or workflow file |
| Template render | a template that no longer renders against every repo entry |
| Template parse | rendered output that isn't valid YAML |
| Placeholder leak | `{{NAME}}` surviving into output |
| SHA pins | a third-party `uses:` on a floating tag, or missing its version comment |
| shellcheck | script bugs, when shellcheck is installed locally |

## Why the placeholder check exists separately

A leaked `{{SERVICE_NAME}}` is often *valid YAML*. It parses fine and fails
only when the workflow actually runs, in someone else's repo. Parsing alone
doesn't catch it, so the check is a distinct step.

Detect it in Python, not with `grep`: a bare `{{` also matches GitHub's own
`${{ }}` expressions, and some greps (ugrep) reject `{{` outright as a
malformed repeat quantifier. `check_templates.py` uses a `(?<!\$)` lookbehind.

## What verify.sh does not cover

**Behaviour.** It proves the YAML is well-formed and the templates render; it
never executes a `run:` block. For new shell or Python logic, dry-run it
outside GitHub Actions:

1. Extract the `run:` string with `yaml.safe_load` — this also proves what the
   block scalar's indentation actually collapses to.
2. Substitute any `${{ github.* }}` expressions by hand. Bash chokes on a
   literal `${{ }}`; that's a test-harness artifact, not a real bug.
3. Stub out `curl`, `gh`, and anything else that would hit the network.
4. Run it with `bash`, covering the failure paths as well as the happy one.

**Workflow semantics.** `actionlint` covers that, and runs in CI: invalid
`${{ }}` expressions, bad `needs:` references, a key used in a context that
doesn't provide it, plus shellcheck over every `run:` block. Install it
locally if you're changing workflow logic.

## Adding a check

Confirm it fails on deliberately broken input before you trust it. A check
that can't go red reads as coverage that isn't there — worse than no check,
because it stops anyone looking.

Both existing checkers were validated this way: the pin check against an
injected `@v4`, the template check against a typo'd placeholder.

## Known gaps

- Nothing renders the *installed* pipeline against a real repo. The templates
  are verified as YAML, not executed.
- `actionlint` reads `.github/workflows/` only. It does not lint composite
  `action.yml` files or `pipelines/templates/*.tmpl`.
- Nothing detects a stale SHA pin — only an unpinned one.

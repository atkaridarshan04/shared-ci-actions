# Verifying a change

```
./scripts/verify.sh
```

No arguments, runnable from anywhere. Exactly what CI runs — pass locally,
pass in CI.

| Check | Catches |
|---|---|
| YAML syntax | a malformed action or workflow file |
| Template render | a template that no longer renders against every repo entry |
| Template parse | rendered output that isn't valid YAML |
| Placeholder leak | `{{NAME}}` surviving into output |
| SHA pins | a third-party `uses:` on a floating tag, or missing its version comment |
| shellcheck | script bugs, when installed locally |

**Why the placeholder check is separate:** a leaked `{{SERVICE_NAME}}` is
often *valid YAML*. It parses fine and fails only at runtime, in someone
else's repo. Detect it in Python, not `grep` — a bare `{{` also matches
GitHub's `${{ }}`, and ugrep rejects `{{` as a malformed quantifier.
`check_templates.py` uses a `(?<!\$)` lookbehind.

## What it doesn't cover

**Behaviour.** Nothing executes a `run:` block. Dry-run new shell or Python
logic outside Actions:

1. Extract the `run:` string with `yaml.safe_load` — this also proves what the
   block scalar's indentation collapses to.
2. Substitute `${{ github.* }}` by hand. Bash chokes on a literal `${{ }}`;
   that's a harness artifact, not a bug.
3. Stub `curl`, `gh`, anything touching the network.
4. Run with `bash`, covering failure paths, not just the happy one.

**Workflow semantics.** `actionlint` covers those in CI — invalid `${{ }}`,
bad `needs:`, a key in a context that doesn't provide it, plus shellcheck on
every `run:` block.

## Adding a check

Confirm it fails on deliberately broken input first. A check that can't go red
reads as coverage that isn't there — worse than none, because it stops anyone
looking. Both existing checkers were validated this way: the pin check against
an injected `@v4`, the template check against a typo'd placeholder.

## Known gaps

- Nothing runs an *installed* pipeline. Templates are verified as YAML, not
  executed.
- `actionlint` reads `.github/workflows/` only — not composite `action.yml`
  files or templates.
- Nothing detects a *stale* SHA pin, only an unpinned one. See
  [versioning](versioning.md).

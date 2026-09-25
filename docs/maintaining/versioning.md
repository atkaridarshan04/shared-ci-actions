# Versioning, releases, and keeping pins current

Consumers reference these actions by ref:

```yaml
- uses: atkaridarshan04/shared-ci-actions/.github/actions/build-candidate-image@main
```

Whatever that ref resolves to is what runs in their pipeline. That makes the
ref the whole API surface, and it's why this page exists.

## The problem with `@main`

The templates currently point at `@main`. That means **every commit here
reaches every consumer on their next run**, with no way for them to pin, stage
an upgrade, or roll back. A bad merge is a fleet-wide incident, not a revert.

CLAUDE.md already forbids `@main` for third-party actions, for exactly this
reason. Pointing consumers at our own `@main` is the same risk aimed inward.

## The release scheme

[`release.yml`](workflows.md#releaseyml) cuts an immutable `vX.Y.Z` tag and
force-moves a `vX` tag to it — the scheme `actions/checkout` and friends use.

| Ref | Mutability | Who should use it |
|---|---|---|
| `@v1.2.0` | never moves | pinning to an exact release |
| `@v1` | moves on every 1.x release | **the normal choice** — fixes, no breaking changes |
| `@main` | moves on every commit | this repo's own testing, nothing else |

The force-push applies only to the major tag. That's not a workaround — a
moving major tag is what makes `@v1` mean "latest 1.x", and it's the one tag
that's *supposed* to move.

To cut a release: dispatch `release.yml` with a bare `X.Y.Z`. It refuses a
leading `v`, a prerelease suffix, and any version that already exists, and it
runs `verify.sh` first so a release can't be cut from a broken tree.

### After the first release

Change the refs in `pipelines/templates/*.tmpl` from `@main` to `@v1`. That's
the one-line change that makes all of the above real; until `v1` exists there
is no pinned ref to point at.

## What counts as a breaking change

For a composite action, the contract is its inputs, its outputs, and its
observable side effects. Bump **major** for:

- removing or renaming an input or output
- making an optional input required
- changing a default in a way that changes behaviour for someone who didn't
  set it (e.g. flipping `fail-on-findings` to `false`)
- changing what a step writes, pushes, or tags

Bump **minor** for a new optional input with a backward-compatible default, or
a new action. **Patch** for fixes that don't change the contract.

Two that look safe and are not:

- **Tightening a gate.** Making a scan stricter breaks builds that passed
  yesterday. Technically compatible, practically a major.
- **Changing a tag format.** `promote-candidate-image` emits
  `<sha>-<component>`; anything downstream parsing that will break.

## Dependabot

[`.github/dependabot.yml`](../../.github/dependabot.yml) watches the
`github-actions` ecosystem weekly and opens PRs bumping SHA pins, with the
version comment updated.

This is what makes pinning sustainable. Pinned *without* it, pins rot: the
SHAs stay frozen while the actions move on, and the convention becomes a
liability — you get the maintenance cost of pinning with none of the currency
of floating.

### Its blind spot

Dependabot reads `.github/workflows/` and composite `action.yml` files. It
does **not** read `pipelines/templates/*.tmpl` — they aren't workflow files as
far as it's concerned.

So template pins are manual. `verify.sh` enforces that they stay *pinned* and
carry a version comment, but nothing tells you they've gone *stale*. When
Dependabot bumps an action in an `action.yml`, check whether the same action
appears in a template and bump it by hand:

```
grep -rn 'uses:.*@' pipelines/templates/
gh api repos/<owner>/<repo>/commits/<tag> --jq .sha
```

This is the most likely thing on this page to be silently wrong six months
from now.

## Communicating a release

There's no changelog file. For a repo whose consumers are pipelines rather
than humans, the tag message and the PR history are usually enough — but if
you cut a major, the consumers won't find out from Dependabot (it doesn't
track this repo's own tags in their repos unless they use `@vX.Y.Z`). Tell
them, or expect `@v1` consumers to sit on v1 forever.

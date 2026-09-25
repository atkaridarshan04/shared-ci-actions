# Versioning, releases, and pins

Consumers reference these actions by ref, so **the ref is the whole API
surface**:

```yaml
- uses: atkaridarshan04/shared-ci-actions/.github/actions/build-candidate-image@main
```

`@main` means every commit here reaches every consumer on their next run —
no pinning, no staged upgrade, no rollback. A bad merge becomes a fleet-wide
incident. CLAUDE.md already forbids `@main` for third-party actions; this is
the same risk aimed inward.

## The release scheme

[`release.yml`](workflows.md#releaseyml) cuts an immutable `vX.Y.Z` tag and
force-moves `vX` to it — the scheme `actions/checkout` uses.

| Ref | Moves | Use it for |
|---|---|---|
| `@v1.2.0` | never | pinning to an exact release |
| `@v1` | every 1.x release | **the normal choice** — fixes, no breaking changes |
| `@main` | every commit | this repo's own testing only |

Force-pushing applies only to the major tag — a moving `vX` is what makes
`@v1` mean "latest 1.x".

Dispatch with a bare `X.Y.Z`. It rejects a leading `v`, prerelease suffixes,
and existing versions, and runs `verify.sh` so a release can't come from a
broken tree.

### Pointing pipelines at the release

Set `actions_ref: v1` in `pipelines/repos.yaml` — one value renders into every
`uses:` of every generated pipeline. It ships as `main` because until `v1`
exists there's nothing to point at.

`release.yml` **checks** this rather than doing it: cutting `v2.0.0` while
`actions_ref` is still `v1` fails with an explanation. Automating the rewrite
would mean pushing a commit mid-release, and the ordering is a trap — commit
after tagging and `v1.0.0` points at a tree still saying `main`; commit before
and your release workflow pushes to `main`, which breaks under branch
protection. A major bump is also a breaking change, which is exactly when a
human should be deciding and telling consumers.

## What counts as breaking

The contract is an action's inputs, outputs, and observable side effects.
**Major** for:

- removing or renaming an input or output
- making an optional input required
- changing a default that changes behaviour for someone who never set it
- changing what a step writes, pushes, or tags

**Minor** for a new optional input with a compatible default, or a new action.
**Patch** for fixes that don't touch the contract.

Two that look safe and aren't:

- **Tightening a gate** — a stricter scan breaks builds that passed
  yesterday. Technically compatible, practically major.
- **Changing a tag format** — `promote-candidate-image` emits
  `<sha>-<component>`; anything parsing that breaks.

## Dependabot

[`.github/dependabot.yml`](../../.github/dependabot.yml) watches the
`github-actions` ecosystem weekly and opens PRs bumping SHA pins.

This is what makes pinning sustainable. Without it pins rot — you get the
maintenance cost of pinning and none of the currency of floating.

**Blind spot:** it reads `.github/workflows/` and composite `action.yml` files,
not `pipelines/templates/*.tmpl`. Template pins are manual. `verify.sh` proves
they stay *pinned*, but nothing tells you they're *stale*. When Dependabot
bumps an action, check whether a template uses it too:

```
grep -rn 'uses:.*@' pipelines/templates/
gh api repos/<owner>/<repo>/commits/<tag> --jq .sha
```

This is the most likely thing here to be quietly wrong in six months.

## Announcing a release

There's no changelog — tag messages and PR history are enough for consumers
that are pipelines. But Dependabot won't tell anyone about a **major**: it
doesn't track this repo's tags unless they pin `@vX.Y.Z`. Tell them, or expect
`@v1` consumers to sit on v1 forever.

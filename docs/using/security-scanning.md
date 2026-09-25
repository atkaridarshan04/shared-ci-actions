# Security scanning: what blocks, and what to do about it

Two gates run on every PR into `develop`, and both **fail the build** by
default. This is the page to read when one of them turns your PR red.

| Gate | Scans | Threshold | Can it be turned off? |
|---|---|---|---|
| Semgrep | source code | every finding (`--error`) | **No** — no input exposes it |
| Trivy | the built image | `HIGH` + `CRITICAL`, fixable only | Yes — `fail-on-findings: false` |

That asymmetry is real and worth knowing: `trivy-scan-and-comment` takes a
`fail-on-findings` input, `semgrep-scan-and-comment` does not. Semgrep's
blocking behaviour is hardcoded.

Both post a sticky PR comment (headers `semgrep-scan` and `trivy-scan`) that
updates in place rather than piling up, and both upload their full report as
a workflow artifact — `semgrep-report` and `trivy-reports`. The comment is
truncated at 60,000 characters; the artifact never is. Both steps run with
`if: always()`, so you get the report even when the gate fails.

## Why Trivy ignores unfixed vulnerabilities

`ignore-unfixed: true` means Trivy only reports vulnerabilities that have a
fix available. An unpatched CVE in the base image, with no fixed version
published, will not block you — because there is no action you could take
that would clear it. Blocking on those trains people to disable the gate,
which costs more than the finding.

It also means a clean Trivy run is not "no vulnerabilities". It's "nothing
you can currently fix".

## When a gate blocks you

**First, read the finding.** Both comments name the rule or CVE, the file or
package, and a link. Most findings in a failing PR are real.

In rough order of preference:

### 1. Fix it

The default. For Trivy this is usually a dependency bump or a base-image
bump — the report gives you the fixed version.

### 2. Suppress a genuine Semgrep false positive

Inline, on the line above the finding:

```python
# nosemgrep: python.lang.security.audit.some-rule-id
subprocess.run(cmd, shell=True)   # cmd is a hardcoded constant, see above
```

Always name the specific rule ID. A bare `# nosemgrep` disables every rule on
that line, including ones that haven't been written yet.

### 3. Suppress an unactionable Trivy CVE

Add it to `.trivyignore` in the repo root:

```
# CVE-2024-12345 — openssl, transitive via base image.
# Not exploitable: we never parse untrusted certs.
# Recheck after the next base-image bump. Added 2026-01-15 by @you.
CVE-2024-12345
```

`.trivyignore` has no expiry mechanism, so an entry lives forever unless
someone removes it. The date and reason are the only thing that makes a
future cleanup possible.

### 4. Turn the gate off

```yaml
      - uses: .../trivy-scan-and-comment@main
        with:
          fail-on-findings: "false"
```

This makes Trivy report-only for the whole job.

## Proposed policy

> These are defaults, not something enforced by the tooling. Edit them to
> match how you actually want to work — but decide deliberately, because the
> failure mode here is well documented: in the setup this repo came from,
> `continue-on-error: true` had silently neutralized the container-scan gate
> in about two-thirds of repos. Nobody decided that; it accumulated.

1. **Every suppression carries a reason, inline, next to it.** A bare
   `# nosemgrep` or a lone CVE line in `.trivyignore` should not survive
   review.
2. **Suppress the narrowest thing that works.** A specific rule ID on a
   specific line, or a specific CVE — never a whole ruleset, never a whole
   job.
3. **`fail-on-findings: false` is not acceptable on `dev-pipeline.yml`.** The
   dev gate is the one that runs on every PR; a repo that disables it has no
   container scanning worth the name. If a repo genuinely can't pass today,
   that's a tracked exception with an owner, not a config default.
4. **A new suppression is a review conversation.** It's the one change where
   "LGTM" from someone who didn't read the finding is actively harmful.

## Tuning what Semgrep runs

`semgrep_configs` is per-repo, in
[`pipelines/repos.yaml`](../../pipelines/repos.yaml), and should match the
repo's actual stack. Running `p/react` against a Python service costs time and
produces nothing; omitting `p/sql-injection` from a service with a database is
how a real finding gets missed.

Changing it takes effect on the next pipeline install or template render — see
[`install-pipeline.md`](install-pipeline.md).

## Where each gate runs

| | Semgrep | Trivy |
|---|---|---|
| `dev-pipeline.yml` (PR) | yes | yes, on the candidate image |
| `dev-pipeline.yml` (merge) | no | no — the image was already scanned, and is promoted by digest |
| `qa-release.yml` | no | yes, on the release-branch build |

The merge path deliberately re-scans nothing: it promotes the exact digest
that was scanned on the PR. See
[`dev-pipeline.md`](dev-pipeline.md#design-principle-build-once-promote-by-digest).

QA has no Semgrep job today. The source was scanned on the dev PR, but a
`release-*` branch carrying cherry-picks that never went through one would not
be re-scanned — worth knowing if you cherry-pick into releases.

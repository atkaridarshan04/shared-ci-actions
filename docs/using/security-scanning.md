# Security scanning: what blocks, and what to do

Four gates run on every PR into `develop`, and the three source scans (Semgrep, Gitleaks, dependencies) also run before the QA build. All **fail the build** by default, and the image is built and pushed only if they pass.

| Gate | Scans | Blocks on | Can it be disabled? |
|---|---|---|---|
| Semgrep | source code | `ERROR` by default (`fail-on-severity`) | **No** — the input takes severities only, never "off" |
| Gitleaks | every commit the PR adds, for committed secrets | any finding | **No** |
| Trivy (dependencies) | the repo's manifests and lockfiles | `HIGH`/`CRITICAL`, fixable only | Yes — `fail-on-findings: false` |
| Trivy (image) | the built image | `HIGH`/`CRITICAL`, fixable only | Yes — `fail-on-findings: false` |

Semgrep's threshold is tunable but the gate itself isn't removable: `fail-on-severity`
accepts `ERROR`, `WARNING`, or `INFO` and nothing else. Findings below the
threshold are still scanned, reported, and commented — they just don't gate
the merge. Semgrep is also pinned to a fixed release, so a new Semgrep version
can't start failing your builds without someone here bumping it deliberately.

Both post a sticky PR comment that updates in place, and upload the full
report as an artifact (`semgrep-report`, `trivy-reports`). Comments truncate
at 60k characters; artifacts don't. Both run `if: always()`, so you get the
report even when the gate fails.

**A clean Trivy run isn't "no vulnerabilities"** — `ignore-unfixed` means
"nothing you can currently fix". Blocking on CVEs with no published fix just
teaches people to disable the gate.

## When a gate blocks you

Read the finding first — it names the rule or CVE, the file or package, and a
link. Most findings on a failing PR are real.

**1. Fix it.** The default. For Trivy that's usually a dependency or
base-image bump; the report gives you the fixed version.

**2. Suppress a genuine Semgrep false positive** — inline, above the finding:

```python
# nosemgrep: python.lang.security.audit.some-rule-id
subprocess.run(cmd, shell=True)   # cmd is a hardcoded constant
```

Name the specific rule ID. A bare `# nosemgrep` disables every rule on that
line, including ones not yet written.

**3. Suppress an unactionable Trivy CVE** — `.trivyignore` in the repo root:

```
# CVE-2024-12345 — openssl, transitive via base image.
# Not exploitable: we never parse untrusted certs.
# Recheck after the next base-image bump. Added 2026-01-15 by @you.
CVE-2024-12345
```

`.trivyignore` has no expiry, so entries live forever unless someone removes
them. The date and reason are what make cleanup possible later.

**4. Turn the gate off** — `fail-on-findings: "false"` makes Trivy
report-only for the whole job. Semgrep has no equivalent; the closest is
raising `fail-on-severity`, which still blocks at the level you name.

## Policy

> Defaults, not enforced by tooling — edit to suit. But decide deliberately:
> in the setup this repo came from, `continue-on-error: true` had silently
> neutralized the container-scan gate in about two-thirds of repos. Nobody
> chose that; it accumulated because nothing was written down.

1. **Every suppression carries a reason, inline.** A bare `# nosemgrep` or a
   lone CVE line shouldn't survive review.
2. **Suppress the narrowest thing that works** — one rule on one line, one
   CVE. Never a ruleset, never a job.
3. **`fail-on-findings: false` is not acceptable on `dev-pipeline.yml`.** A
   repo that can't pass today is a tracked exception with an owner, not a
   config default.
4. **A new suppression is a review conversation** — the one change where a
   rubber-stamp "LGTM" is actively harmful.

## Where each gate runs

| | Semgrep | Gitleaks | Trivy deps | Trivy image |
|---|---|---|---|---|
| dev PR | yes | PR's commits | yes | yes, on the candidate |
| dev merge | no | no | no | yes, on the rebuild |
| QA (`release-*`) | yes | tree only | yes | yes, on the release build |

Off a PR there is no commit range, so Gitleaks scans the checked-out tree, not history, and nothing is commented on a PR.

## Secrets

Gitleaks scans every commit the PR adds, so a secret committed and then deleted still fails. **A leaked secret is already compromised - rotate it first**, then rewrite the branch to drop the commit.

Rules come from a shared baseline, [`gitleaks.toml`](../../.github/actions/gitleaks-scan/gitleaks.toml): gitleaks' built-ins plus any org-wide additions. For a false positive, add its fingerprint to `.gitleaksignore` with a reason. A repo `.gitleaks.toml` replaces the baseline (start it with `[extend]` / `useDefault = true`), so prefer `.gitleaksignore`.

## Tuning Semgrep

Every repo runs a baseline in the action: `p/dockerfile p/cwe-top-25 p/owasp-top-ten p/r2c-security-audit p/secure-defaults p/secrets`. `semgrep_configs` in [`pipelines/repos.yaml`](../../pipelines/repos.yaml) adds the stack's extra packs (`p/python p/fastapi`, `p/react`). Match the stack: omitting `p/sql-injection` from a DB-backed service risks missing a real finding.

The action skips `github-actions-mutable-action-tag`, which warns on this repo's own `@v1` refs. It also no longer warns on third-party tag pins in a consumer's own workflows.

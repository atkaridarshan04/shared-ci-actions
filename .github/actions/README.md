# Shared CI actions

Composite actions for the dev and QA pipelines: Semgrep + Trivy scanning,
build, push-candidate, promote-on-merge, Helm values update, and PR
resolution. Every app repo's pipeline is a thin caller of these, so the
pipeline is defined once instead of copy-pasted per repo.

Not wrapped here: `docker/login-action` is already a single-line call, so
wrapping it would buy nothing.

## See also

- [`docs/dev-pipeline.md`](../../docs/dev-pipeline.md) - full flow, tagging
  scheme, and failure modes for the PR/`develop` stage
- [`docs/qa-release.md`](../../docs/qa-release.md) - QA flow, and why it
  updates the charts repo through a PR instead of a direct push
- [`docs/github-app-setup.md`](../../docs/github-app-setup.md) - **required**
  one-time setup for the cross-repo credential `update-helm-chart` needs

This README is the per-action usage reference (what input goes where); the
docs above are the design rationale (why the pipeline is shaped this way).

## Pipeline file naming

Every app repo's `.github/workflows/` uses these two names, one per stage:

- **`dev-pipeline.yml`** - PR + push to `develop` (Semgrep, build, Trivy,
  PR-comment, promote-by-digest on merge, values update)
- **`qa-release.yml`** - push to `release-*` (build, Trivy, push, values
  update via PR to `develop`)

`scripts/install-pipeline.sh` renders and installs these from
`pipelines/templates/`; you rarely write them by hand.

## Registry

These actions are registry-agnostic - they only require the calling job to
have logged in before pushing. The templates target GHCR
(`ghcr.io/<owner>/<repo>`), which needs no credential beyond
`secrets.GITHUB_TOKEN` and a `packages: write` permission on the job.

## semgrep-scan-and-comment

```yaml
  semgrep:
    name: Semgrep Scan
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: atkaridarshan04/shared-ci-actions/.github/actions/semgrep-scan-and-comment@main
        with:
          semgrep-configs: >-
            p/python p/fastapi p/dockerfile p/cwe-top-25 p/owasp-top-ten
            p/r2c-security-audit p/secure-defaults p/secrets p/sql-injection
```

## trivy-scan-and-comment

```yaml
      - uses: atkaridarshan04/shared-ci-actions/.github/actions/trivy-scan-and-comment@main
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.CANDIDATE_TAG }}
          label: api image
```

Both scan actions post via the default `GITHUB_TOKEN`, so the calling job
must grant `permissions: pull-requests: write` itself.

On `pull_request` events the PR is auto-detected - no extra input needed. On
a QA run (`release-*` push) there is no PR in context, so pass `pr-number` (resolved via `resolve-pr-for-branch` below) to
both actions; if it's empty the comment step is skipped and only the report
artifact is uploaded, instead of the step failing outright.

```yaml
      - uses: atkaridarshan04/shared-ci-actions/.github/actions/trivy-scan-and-comment@main
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.IMAGE_TAG }}
          label: api image
          pr-number: ${{ steps.pr.outputs.pr-number }}
```

## resolve-pr-for-branch

Run once per job, before the scan steps, on the QA pipeline only (dev's
`pull_request` event carries the PR number already).

```yaml
      - id: pr
        uses: atkaridarshan04/shared-ci-actions/.github/actions/resolve-pr-for-branch@main
        with:
          branch: ${{ github.ref_name }}
```

## validate-branch-jira

Opt-in, wired into no template - `dev-pipeline.yml` doesn't call it. Kept as
a real action rather than ~30 lines of commented-out inline steps, so turning
ticket gating on for a repo is one job, not restoring bit-rotted YAML.

```yaml
  validate-branch-jira:
    name: Validate Branch and Jira Ticket
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: atkaridarshan04/shared-ci-actions/.github/actions/validate-branch-jira@main
        with:
          branch: ${{ github.head_ref }}
          jira-domain: ${{ secrets.JIRA_DOMAIN }}
          jira-user: ${{ secrets.JIRA_USER }}
          jira-token: ${{ secrets.JIRA_API_TOKEN }}
```

## build-candidate-image

Builds and tags only - it never pushes. That's deliberate: the caller scans
the local image first, and logs in + pushes afterwards, so an image that
fails its Trivy gate never reaches the registry.

```yaml
      - uses: atkaridarshan04/shared-ci-actions/.github/actions/build-candidate-image@main
        with:
          image-tag: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.CANDIDATE_TAG }}
          dockerfile-target: runtime      # optional
          build-args: |                   # optional
            APP_ENV=${{ vars.APP_ENV }}
```

## promote-candidate-image

Run in a `push`-triggered job, after registry login. Retags the already-scanned
candidate by digest - no rebuild.

```yaml
  promote-image:
    if: github.event_name == 'push'
    permissions:
      contents: read
      packages: write
      pull-requests: read
    outputs:
      image_tag: ${{ steps.promote.outputs.release-tag }}
    steps:
      - uses: docker/login-action@dbcb813823bdd20940b903addbd779551569679f # v4.6.0
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1
        with: { driver: docker }
      - id: promote
        uses: atkaridarshan04/shared-ci-actions/.github/actions/promote-candidate-image@main
        with:
          component-name: api
          image-repository: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
```

`base-branch` defaults to `develop` - set it if your integration branch has
another name, otherwise no merged PR will be found and the job fails closed.

## update-helm-chart

Run as its own job - it checks out the charts repo into the job root.

The values file lives in a **separate Helm-charts repo**, so this always
needs a cross-repo token. `GITHUB_TOKEN` can *never* work here: it is scoped
to the repo whose workflow generated it, by design, no matter what
`permissions:` you grant. Mint a short-lived App token per run instead -
one-time setup in
[`docs/github-app-setup.md`](../../docs/github-app-setup.md).

```yaml
  update-helm-repo:
    needs: promote-image
    steps:
      - id: helm-app-token
        uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0
        with:
          app-id: ${{ vars.HELM_BOT_APP_ID }}
          private-key: ${{ secrets.HELM_BOT_APP_PRIVATE_KEY }}
          owner: atkaridarshan04
          repositories: test-helm-charts
      - uses: atkaridarshan04/shared-ci-actions/.github/actions/update-helm-chart@main
        with:
          yaml-path: .services.api.imageTag
          helm-repo: atkaridarshan04/test-helm-charts
          values-file: dev/values.yaml
          image-tag: ${{ needs.promote-image.outputs.image_tag }}
          component-label: api
          helm-repo-token: ${{ steps.helm-app-token.outputs.token }}
```

The job needs no special `permissions:` - it never writes to the repo it is
running in.

`mode` defaults to `direct-commit`: push straight to `target-branch`,
re-applying the edit onto the latest remote state if another run pushed
first. Every app repo's dev pipeline targets the same branch of the same
charts repo, so that race is routine, not exotic.

QA uses `mode: pr` instead: it checks out `source-branch` (the release branch
that triggered the run) **in the charts repo**, pushes the update there, and
opens (or reuses) a PR into `target-branch` - so the change lands on
`develop` through review, not a direct push. The charts repo therefore needs
a branch of that name.

```yaml
      - uses: atkaridarshan04/shared-ci-actions/.github/actions/update-helm-chart@main
        with:
          yaml-path: .services.api.imageTag
          helm-repo: atkaridarshan04/test-helm-charts
          values-file: qa/values.yaml
          image-tag: ${{ needs.build-scan-push.outputs.image_tag }}
          component-label: api
          helm-repo-token: ${{ steps.helm-app-token.outputs.token }}
          mode: pr
          source-branch: ${{ github.ref_name }}
          target-branch: develop
```

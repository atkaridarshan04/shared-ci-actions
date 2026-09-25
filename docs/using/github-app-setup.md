# GitHub App setup (charts-repo credential)

**Required.** `update-helm-chart` commits to a separate charts repo, and
`GITHUB_TOKEN` can't reach it — it's scoped to the repo whose workflow
generated it, no matter what `permissions:` you grant. Skip this and the
values-update job fails at checkout.

A PAT would work. An App is better: not tied to a person, installed on one
repo, two permissions, and the token it mints is short-lived and regenerated
each run — no long-lived secret. Works on every plan including Free.

Do this once per app repo that runs a pipeline.

## 1. Create the App

**Settings → Developer settings → GitHub Apps → New GitHub App**, on the
account owning the charts repo.

- **Name**: e.g. `deploy-values-bot` (globally unique across GitHub)
- **Homepage URL**: any placeholder — required field, unused
- **Webhook**: uncheck **Active** — it only mints tokens, never receives events
- **Repository permissions**:
  - **Contents: Read and write** — commit and push `values.yaml`
  - **Pull requests: Read and write** — open/reuse the QA PR (only QA's
    `mode: pr` needs this; dev doesn't)
  - everything else **No access**
- **Where can this be installed?**: *Only on this account*

## 2. App ID → a variable

The settings page shows an **App ID**. Not secret — store as an Actions
**variable** named `HELM_BOT_APP_ID`.

## 3. Private key → a secret

**Private keys → Generate a private key** downloads a `.pem`. *This is the
secret.* Store its full contents, including the `BEGIN`/`END` lines, as an
Actions **secret** named `HELM_BOT_APP_PRIVATE_KEY`.

| Account type | Where |
|---|---|
| Personal | repo-level, in each caller repo — personal accounts have no org secrets |
| Org on Team/Enterprise | org-level, scoped to selected repositories |
| Org on Free | repo-level — org secrets aren't readable by private repos on Free |

## 4. Install it — on the charts repo only

**Install App** → the account → **Only select repositories** → the charts
repo. Not "All repositories": narrowing the credential's reach is the point.

## 5. Use it

In every caller, immediately before `update-helm-chart`:

```yaml
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

The rendered templates already do this — the block is here for reference.
`repositories:` scopes the *generated token* too, on top of the App only being
installed there.

## One behavioural difference

Unlike `GITHUB_TOKEN`, App-token commits **can** trigger workflows. If the
charts repo has its own CI, expect it to fire on every values bump — usually
what you want; just don't put a workflow there that writes back to the same
branch.

## Retiring a PAT this replaces

Revoke it (**Settings → Developer settings → Personal access tokens**) and
delete the secret holding it. Leaving it keeps the blast radius you removed.

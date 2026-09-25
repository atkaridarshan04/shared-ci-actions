# GitHub App setup for the charts-repo credential

**Required setup.** `update-helm-chart` commits to a separate Helm-charts
repo, and `GITHUB_TOKEN` cannot reach it — the token is scoped to the repo
whose workflow generated it, by design, so it can never authenticate against
another repo no matter what `permissions:` you grant. That's a hard limit,
not a misconfiguration, and it's why `helm-repo-token` is a separate input.
Skip this and the values-update job fails at checkout.

A personal access token would work. A GitHub App is better: a bot identity
that isn't tied to any person, installed on exactly one repo, with exactly
the two permissions it needs — unaffected by anyone's password, 2FA, or
offboarding. The token it mints is short-lived and generated fresh each run,
so there's no long-lived credential sitting in a secret. Apps work on every
GitHub plan, including Free.

Do this once per app repo that runs a pipeline.

## 1. Create the App

**Settings → Developer settings → GitHub Apps → New GitHub App**, on the
account that owns the charts repo (your user account, or the org).

- **GitHub App name**: e.g. `deploy-values-bot` (must be globally unique
  across all of GitHub — add a suffix if it's taken)
- **Homepage URL**: any placeholder (required field, unused here)
- **Webhook**: uncheck "Active" — this App only mints installation tokens for
  API and git calls, it never receives events
- **Repository permissions**:
  - **Contents: Read and write** — to commit and push `values.yaml`
  - **Pull requests: Read and write** — to open/list/reuse the QA PR
    (dev alone doesn't need this; QA's `mode: pr` does)
  - Leave every other permission at "No access"
- **Where can this GitHub App be installed?**: "Only on this account"

Click **Create GitHub App**.

## 2. Record the App ID

The App's settings page shows an **App ID** near the top. It isn't secret —
store it as an Actions **variable** named `HELM_BOT_APP_ID`.

## 3. Generate a private key

Same settings page → **Private keys** → **Generate a private key**. This
downloads a `.pem` file — this *is* the secret. Store its full contents,
including the `-----BEGIN/END PRIVATE KEY-----` lines, as an Actions
**secret** named `HELM_BOT_APP_PRIVATE_KEY`.

### Where to put them

| Account type | Where |
|---|---|
| Personal account | Repo-level, in each caller repo. Personal accounts have no org-level secrets. |
| Org on Team/Enterprise | Org-level, scoped to "Selected repositories" — one place to rotate. |
| Org on Free | Repo-level. Org-level secrets are **not** readable by private repos on Free. |

## 4. Install the App — on the charts repo only

From the App's page → **Install App** → choose the account → **Only select
repositories** → the charts repo (`test-helm-charts` in the templates). Do not choose "All repositories": narrowing
this credential's reach to the one repo it needs is the entire point.

## 5. Generate a token per workflow run

In every caller, immediately before `update-helm-chart`:

```yaml
      - name: Generate charts-repo App token
        id: helm-app-token
        uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0
        with:
          app-id: ${{ vars.HELM_BOT_APP_ID }}
          private-key: ${{ secrets.HELM_BOT_APP_PRIVATE_KEY }}
          owner: atkaridarshan04
          repositories: test-helm-charts

      - uses: atkaridarshan04/shared-ci-actions/.github/actions/update-helm-chart@main
        with:
          yaml-path: .services.api.imageTag
          values-file: dev/values.yaml
          helm-repo: atkaridarshan04/test-helm-charts
          image-tag: ${{ needs.promote-image.outputs.image_tag }}
          component-label: api
          helm-repo-token: ${{ steps.helm-app-token.outputs.token }}
```

`repositories:` scopes the *generated token* to that one repo as well — belt
and suspenders on top of the App only being installed there. The token is
short-lived and minted fresh each run, so there's nothing long-lived to leak.

Nothing else about `update-helm-chart` changes; `helm-repo-token` accepts any
bearer token with push access, App-issued or not.

## 6. One behavioural difference to plan for

Unlike `GITHUB_TOKEN`, commits pushed with an App token **can** trigger
workflow runs. If the charts repo has its own CI — an ArgoCD sync check, a
lint job — expect it to fire on every values bump. That's usually what you
want; just don't be surprised by it, and don't put a pipeline in the charts
repo that writes back to the same branch.

## 7. Retire any PAT this replaces

Once every caller is on the App token, revoke the old personal access token
(**Settings → Developer settings → Personal access tokens**) and delete
whatever secret held it. Leaving it in place keeps the blast radius you just
removed.

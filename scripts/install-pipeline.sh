#!/usr/bin/env bash
# Install one pipeline-stage file into one repo, via a PR on that repo.
# Run manually, one repo/stage at a time - not a bulk operation.
set -euo pipefail

OWNER="${GITHUB_OWNER:-atkaridarshan04}"

usage() {
  cat >&2 <<EOF
Usage: $0 <repo-name> <dev|qa> [--force]

  repo-name  e.g. test-api - must have an entry in pipelines/repos.yaml
  stage      dev or qa
  --force    overwrite the stage file if it already exists in the repo

Environment:
  GITHUB_OWNER   repo owner to target (default: $OWNER)
  BASE_BRANCH    branch to clone and open the PR against
                 (default: the repo's integration_branch in pipelines/repos.yaml)

Requires: gh auth login, and PyYAML for the templating step.
EOF
  exit 1
}

[ $# -ge 2 ] || usage
REPO="$1"
STAGE="$2"
FORCE="${3:-}"

case "$STAGE" in dev|qa) ;; *) echo "stage must be dev or qa" >&2; exit 1 ;; esac
case "$FORCE" in ""|--force) ;; *) echo "unknown option: $FORCE" >&2; usage ;; esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$SCRIPT_DIR/lib/pipeline_lib.py"

# render before cloning anything, so a bad config fails without side effects
FILENAME="$(python3 "$LIB" filename "$STAGE")"
RENDERED="$(python3 "$LIB" render "$REPO" "$STAGE")"

# the PR base must match the branch the rendered pipeline triggers on, so it
# comes from the same config rather than a second, independently-set default
BASE_BRANCH="${BASE_BRANCH:-$(python3 "$LIB" config "$REPO" integration_branch)}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "Cloning $OWNER/$REPO ($BASE_BRANCH)..."
gh repo clone "$OWNER/$REPO" "$WORKDIR/repo" -- --depth 1 --branch "$BASE_BRANCH" --quiet

cd "$WORKDIR/repo"
TARGET=".github/workflows/$FILENAME"

if [ -e "$TARGET" ] && [ "$FORCE" != "--force" ]; then
  echo "$TARGET already exists in $OWNER/$REPO. Re-run with --force to replace it." >&2
  exit 1
fi

git checkout -b "ci/add-${STAGE}-pipeline"
mkdir -p .github/workflows
printf '%s' "$RENDERED" > "$TARGET"
python3 -c "import yaml, sys; yaml.safe_load(open(sys.argv[1]))" "$TARGET"

git add "$TARGET"
git commit -m "Add $STAGE pipeline calling shared composite actions"
git push -u origin "ci/add-${STAGE}-pipeline"

# --head explicit: gh's push-detection reads the upstream tracking ref,
# which is unreliable straight after a shallow clone's first push
gh pr create \
  --repo "$OWNER/$REPO" \
  --base "$BASE_BRANCH" \
  --head "ci/add-${STAGE}-pipeline" \
  --title "Add $STAGE pipeline (shared composite actions)" \
  --body "Adds \`$TARGET\`, calling the composite actions in $OWNER/shared-ci-actions instead of inline steps.

See shared-ci-actions' \`docs/using/dev-pipeline.md\` / \`docs/using/qa-release.md\` for the design rationale."

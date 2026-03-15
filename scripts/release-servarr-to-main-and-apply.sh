#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/release-servarr-to-main-and-apply.sh [commit-message]
#
# What this script does:
# 1) Commit all current changes on servarr-stack
# 2) Merge servarr-stack into main locally (no push)
# 3) Apply all Argo CD Application/ApplicationSet manifests from apps/*.yaml

SERVARR_BRANCH="servarr-stack"
MAIN_BRANCH="main"
COMMIT_MSG="${1:-chore: reorganize charts apps manifests and repoint argocd}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd git
require_cmd kubectl
require_cmd rg
require_cmd xargs

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${current_branch}" != "${SERVARR_BRANCH}" ]]; then
  echo "Expected to start on '${SERVARR_BRANCH}', found '${current_branch}'." >&2
  exit 1
fi

echo "Staging all current changes on ${SERVARR_BRANCH}..."
git add -A

if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  echo "Committing changes..."
  git commit -m "${COMMIT_MSG}"
fi

echo "Switching to ${MAIN_BRANCH}..."
git checkout "${MAIN_BRANCH}"

echo "Merging ${SERVARR_BRANCH} into ${MAIN_BRANCH}..."
git merge --no-ff "${SERVARR_BRANCH}"

echo "Applying Argo CD apps from apps/*.yaml..."
rg -l '^kind:\s*(Application|ApplicationSet)$' apps/*.yaml | xargs -r -n1 kubectl apply -f

echo
echo "Done."
echo "- Local merge complete: ${SERVARR_BRANCH} -> ${MAIN_BRANCH}"
echo "- Apps applied from apps/*.yaml"
echo "- No push performed"

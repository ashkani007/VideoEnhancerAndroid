#!/usr/bin/env bash
# Export Great History Makers into its own repository (for a new PRIVATE GitHub repository), leaving the
# LensPrompt Android repository untouched.
#
#   tools/export_ghm_repo.sh <target_dir> [--with-videos]
#
# - Snapshot of great_history_makers/ as the new repository root, one initial commit, no LensPrompt history.
# - By default the old preview/final videos under output/ (about 700 MB, files up to 91 MB) stay behind in the old
#   repository; --with-videos copies them and tracks *.mp4 with Git LFS (needs git-lfs; GitHub's free LFS quota is 1 GB).
# - Machine files (local_paths.cmd, candidates/, caches) are never exported.
# - Prints the next commands; it never pushes and never asks for credentials.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DST="${1:?usage: export_ghm_repo.sh <target_dir> [--with-videos]}"
WITH_VIDEOS="${2:-}"
[ -e "$DST" ] && { echo "target $DST already exists"; exit 1; }
mkdir -p "$DST"
EXCLUDES=(--exclude '.git' --exclude '__pycache__' --exclude 'cache/' --exclude 'comfyui/candidates/'
          --exclude 'comfyui/worker/local_paths.cmd' --exclude '*.part' --exclude 'ghm4/tests/out/*.jpg' --exclude 'ghm4/tests/out/*.png')
if [ "$WITH_VIDEOS" != "--with-videos" ]; then
  EXCLUDES+=(--exclude 'output/**/*.mp4' --exclude 'GreatHistoryMakers/**/*.mp4')
fi
# only files git tracks (no stray local renders), copied with their paths
( cd "$SRC" && git ls-files -z . ) | ( cd "$SRC" && rsync -a --from0 --files-from=- "${EXCLUDES[@]}" ./ "$DST/" )
cd "$DST"
git init -q -b main
if [ "$WITH_VIDEOS" = "--with-videos" ]; then
  git lfs install --local >/dev/null && git lfs track "*.mp4" >/dev/null
fi
git add -A
git -c user.name="GHM export" -c user.email="ghm-export@localhost" commit -q -m "Great History Makers: initial import from VideoEnhancerAndroid/great_history_makers"
echo "exported $(git ls-files | wc -l) files, $(du -sh --exclude=.git . | cut -f1) to $DST"
echo "next: create an EMPTY private repository on GitHub (no README), then:"
echo "  git -C \"$DST\" remote add origin https://github.com/<you>/<new-private-repo>.git"
echo "  git -C \"$DST\" push -u origin main        # Git Credential Manager handles sign-in; never paste tokens"

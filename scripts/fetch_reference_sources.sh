#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT_DIR/reference_sources"
mkdir -p "$DEST"

clone_and_pin() {
  local url="$1"
  local dir="$2"
  local sha="$3"
  if [ ! -d "$DEST/$dir/.git" ]; then
    git clone "$url" "$DEST/$dir"
  fi
  git -C "$DEST/$dir" fetch --all --tags
  git -C "$DEST/$dir" checkout "$sha"
}

clone_and_pin "https://github.com/hghero/HeroQuest.git" "hghero" "a89df683c6eaa66942ebec80edf6dd31e8eb5eda"
clone_and_pin "https://github.com/g1augusto/HeroQuestCS50Builder.git" "builder" "19e475fc07b8263d98ca2497de544a53f55e3677"

echo "References fetched in $DEST"

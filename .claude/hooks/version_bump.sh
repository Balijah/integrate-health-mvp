#!/bin/bash
# Version bump hook — runs after git commits to main
# Bumps frontend/public/version.json and appends to CHANGELOG.md
#
# Commit message conventions:
#   feat: ...     → bumps MINOR (1.0.0 → 1.1.0)
#   breaking: ... → bumps MAJOR (1.0.0 → 2.0.0)
#   anything else → bumps PATCH (1.0.0 → 1.0.1)

COMMAND="${CLAUDE_TOOL_INPUT_COMMAND:-}"
EXIT_CODE="${CLAUDE_TOOL_EXIT_CODE:-1}"

# Only run after successful git commit
if ! echo "$COMMAND" | grep -qE "git commit"; then
  exit 0
fi
if [ "$EXIT_CODE" != "0" ]; then
  exit 0
fi

# Only on main branch
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [[ "$BRANCH" != "main" && "$BRANCH" != "production" ]]; then
  exit 0
fi

VERSION_FILE="frontend/public/version.json"

# Create if missing
if [ ! -f "$VERSION_FILE" ]; then
  mkdir -p "$(dirname "$VERSION_FILE")"
  echo '{"major":1,"minor":0,"patch":0,"version":"1.0.0","built_at":"","git_hash":"","branch":"main"}' > "$VERSION_FILE"
fi

MAJOR=$(python3 -c "import json; d=json.load(open('$VERSION_FILE')); print(d.get('major',1))")
MINOR=$(python3 -c "import json; d=json.load(open('$VERSION_FILE')); print(d.get('minor',0))")
PATCH=$(python3 -c "import json; d=json.load(open('$VERSION_FILE')); print(d.get('patch',0))")
OLD="$MAJOR.$MINOR.$PATCH"

LAST_MSG=$(git log -1 --format="%s" 2>/dev/null)

if echo "$LAST_MSG" | grep -qiE "^(feat|feature):"; then
  MINOR=$((MINOR + 1)); PATCH=0; TYPE="minor"
elif echo "$LAST_MSG" | grep -qiE "^(break|breaking|major):"; then
  MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0; TYPE="major"
else
  PATCH=$((PATCH + 1)); TYPE="patch"
fi

NEW="$MAJOR.$MINOR.$PATCH"
BUILT_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

cat > "$VERSION_FILE" << EOF
{
  "major": $MAJOR,
  "minor": $MINOR,
  "patch": $PATCH,
  "version": "$NEW",
  "built_at": "$BUILT_AT",
  "git_hash": "$GIT_HASH",
  "branch": "$BRANCH"
}
EOF

# Update CHANGELOG.md
CHANGELOG="CHANGELOG.md"
if [ ! -f "$CHANGELOG" ]; then
  printf "# Changelog — Integrate Health MVP\n\n---\n\n" > "$CHANGELOG"
fi

ENTRY="## [$NEW] — $(date -u +"%Y-%m-%d") — $GIT_HASH\n- $LAST_MSG\n"
TEMP=$(mktemp)
head -4 "$CHANGELOG" > "$TEMP"
printf "\n$ENTRY" >> "$TEMP"
tail -n +5 "$CHANGELOG" >> "$TEMP"
mv "$TEMP" "$CHANGELOG"

git add "$VERSION_FILE" "$CHANGELOG" 2>/dev/null

echo ""
echo "  📦 Version: $OLD → $NEW ($TYPE bump)"
echo "  📝 CHANGELOG.md updated"
echo ""

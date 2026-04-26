#!/bin/bash
# One-time dev setup for Integrate Health
# Run: bash scripts/install_hooks.sh

set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔧 Installing Integrate Health dev hooks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Git pre-commit hook
echo "▶ Installing git pre-commit hook..."
cp scripts/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "  ✅ .git/hooks/pre-commit installed"

# Claude Code hook permissions
echo "▶ Setting Claude Code hook permissions..."
chmod +x .claude/hooks/pre_deploy_guard.sh
chmod +x .claude/hooks/version_bump.sh
echo "  ✅ Claude Code hooks executable"

# Initialize version.json
VERSION_FILE="frontend/public/version.json"
echo "▶ Checking version.json..."
if [ ! -f "$VERSION_FILE" ]; then
  mkdir -p "$(dirname "$VERSION_FILE")"
  GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "initial")
  cat > "$VERSION_FILE" << EOF
{
  "major": 1,
  "minor": 0,
  "patch": 0,
  "version": "1.0.0",
  "built_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "git_hash": "$GIT_HASH",
  "branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")"
}
EOF
  echo "  ✅ Created version.json (v1.0.0)"
else
  V=$(python3 -c "import json; print(json.load(open('$VERSION_FILE')).get('version','unknown'))" 2>/dev/null || echo "unknown")
  echo "  ✅ version.json exists — current version: $V"
fi

# CHANGELOG
echo "▶ Checking CHANGELOG.md..."
if [ ! -f "CHANGELOG.md" ]; then
  cat > CHANGELOG.md << 'EOF'
# Changelog — Integrate Health MVP

All notable changes documented here automatically on commits to main.

---

## [1.0.0] — Initial release
- MVP: audio recording, Deepgram transcription, Claude SOAP note generation
- Pilot client: Kare Health

EOF
  echo "  ✅ CHANGELOG.md created"
else
  echo "  ✅ CHANGELOG.md already exists"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Setup complete!"
echo ""
echo "  Slash commands available in Claude Code:"
echo "  /regression_test      — Full regression check"
echo "  /security_audit       — Security vulnerability scan"
echo "  /financial_audit      — Cost analysis"
echo "  /hipaa_audit          — HIPAA compliance assessment"
echo "  /onboard_patient_flow — First-visit flow verification"
echo "  /db_migration_check   — Safe migration review"
echo "  /context_refresh      — Project state for new sessions"
echo ""
echo "  Commit conventions for version bumping:"
echo "  feat: ...     → MINOR bump"
echo "  breaking: ... → MAJOR bump"
echo "  fix: ...      → PATCH bump (default)"
echo ""

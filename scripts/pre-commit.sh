#!/bin/bash
# Git pre-commit hook for Integrate Health
# Runs on every commit: lint, type check, secret scan

set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔍 Pre-commit — Integrate Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FAILURES=0

# Python lint on staged .py files
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM | grep "\.py$" || true)
if [ -n "$STAGED_PY" ]; then
  echo "▶ Python lint (ruff)..."
  # Activate venv if present; fall back to system ruff if not
  RUFF_CMD=""
  if [ -f "backend/venv/bin/ruff" ]; then
    RUFF_CMD="backend/venv/bin/ruff"
  elif command -v ruff &>/dev/null; then
    RUFF_CMD="ruff"
  fi
  if [ -z "$RUFF_CMD" ]; then
    echo "  ⚠️  ruff not found — skipping Python lint"
  else
    PY_FILES=$(echo "$STAGED_PY" | sed 's|backend/||g')
    if (cd backend && echo "$PY_FILES" | xargs ../$RUFF_CMD check 2>&1); then
      echo "  ✅ Python lint passed"
    else
      echo "  ❌ Ruff errors found"
      FAILURES=$((FAILURES + 1))
    fi
  fi
fi

# TypeScript check on staged .ts/.tsx files
STAGED_TS=$(git diff --cached --name-only --diff-filter=ACM | grep -E "\.(ts|tsx)$" || true)
if [ -n "$STAGED_TS" ]; then
  echo "▶ TypeScript check..."
  if cd frontend && npx tsc --noEmit 2>&1 | grep -c "error TS" | grep -q "^0$"; then
    echo "  ✅ TypeScript passed"
    cd ..
  else
    echo "  ❌ TypeScript errors found"
    cd ..
    FAILURES=$((FAILURES + 1))
  fi
fi

# Secret scan on all staged files
# Excludes: this hook script itself, instruction_files/ (docs that mention patterns)
echo "▶ Secret scan..."
STAGED_ALL=$(git diff --cached --name-only --diff-filter=ACM || true)
FOUND_SECRET=false
PATTERNS=("sk-ant-" "AKIA[A-Z0-9]{16}" "dg_" "postgres://.*:.*@.*@")
SCAN_EXCLUDES="scripts/pre-commit.sh instruction_files/"
for file in $STAGED_ALL; do
  # Skip excluded paths
  SKIP=false
  for excl in $SCAN_EXCLUDES; do
    if [[ "$file" == "$excl" || "$file" == "$excl"* ]]; then
      SKIP=true; break
    fi
  done
  [ "$SKIP" = true ] && continue

  if [ -f "$file" ]; then
    for pat in "${PATTERNS[@]}"; do
      if git diff --cached "$file" | grep -qE "$pat"; then
        echo "  ❌ Possible secret in $file — pattern: $pat"
        FOUND_SECRET=true
        FAILURES=$((FAILURES + 1))
      fi
    done
  fi
done
if [ "$FOUND_SECRET" = false ]; then
  echo "  ✅ No secrets detected"
fi

# Block .env commit
if git diff --cached --name-only | grep -qE "^\.env$"; then
  echo "  ❌ BLOCKED: .env file staged for commit — add to .gitignore"
  FAILURES=$((FAILURES + 1))
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILURES -gt 0 ]; then
  echo ""
  echo "  🚫 $FAILURES check(s) failed — commit blocked."
  echo "  Bypass (emergency): git commit --no-verify"
  echo ""
  exit 1
else
  echo ""
  echo "  ✅ All checks passed."
  echo ""
  exit 0
fi

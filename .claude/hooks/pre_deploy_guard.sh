#!/bin/bash
# Pre-deploy regression guard for Integrate Health MVP
# Intercepts deploy commands and runs a gate before allowing them.
# Triggers on: ./deploy.sh, bash deploy.sh, any variant

COMMAND="${CLAUDE_TOOL_INPUT_COMMAND:-}"
IS_DEPLOY=false

if echo "$COMMAND" | grep -qE "(deploy\.sh|git push (origin )?(main|production|master))"; then
  IS_DEPLOY=true
fi

if [ "$IS_DEPLOY" = false ]; then
  exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚦 PRE-DEPLOY REGRESSION GATE — Integrate Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Detected: $COMMAND"
echo ""

FAILURES=0

# Check 1: TypeScript type check
echo "▶ [1/3] TypeScript type check..."
if cd frontend && npx tsc --noEmit 2>&1; then
  echo "  ✅ TypeScript passed"
  cd ..
else
  echo "  ❌ TypeScript errors found"
  cd ..
  FAILURES=$((FAILURES + 1))
fi

# Check 2: Python lint
echo ""
echo "▶ [2/3] Python lint (ruff)..."
if cd backend && source venv/bin/activate 2>/dev/null && ruff check app/ 2>&1; then
  echo "  ✅ Python lint passed"
  cd ..
else
  echo "  ⚠️  Ruff issues found (review above) — non-blocking"
  cd ..
fi

# Check 3: Backend tests (if test suite exists)
echo ""
echo "▶ [3/3] Backend tests..."
if [ -d "backend/tests" ] && [ "$(find backend/tests -name 'test_*.py' | wc -l)" -gt 0 ]; then
  if cd backend && source venv/bin/activate 2>/dev/null && pytest tests/ -q --tb=short 2>&1; then
    echo "  ✅ Tests passed"
    cd ..
  else
    echo "  ❌ Tests FAILED"
    cd ..
    FAILURES=$((FAILURES + 1))
  fi
else
  echo "  ⚠️  No test suite found — skipping"
fi

# Check 4: No uncommitted changes to critical files
echo ""
echo "▶ Checking for uncommitted critical changes..."
DIRTY=$(git diff --name-only 2>/dev/null | grep -E "(migration|models|auth|security)" | head -5)
if [ -n "$DIRTY" ]; then
  echo "  ⚠️  Uncommitted changes to critical files:"
  echo "$DIRTY"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $FAILURES -gt 0 ]; then
  echo ""
  echo "  🚫 DEPLOY BLOCKED — $FAILURES check(s) failed."
  echo "  Fix failures above, then re-run deploy."
  echo "  Emergency override: SKIP_DEPLOY_GATE=1 ./deploy.sh"
  echo ""
  if [ "${SKIP_DEPLOY_GATE:-0}" = "1" ]; then
    echo "  ⚠️  Override active — proceeding despite failures."
    exit 0
  fi
  exit 1
else
  echo ""
  echo "  ✅ All checks passed — deploy cleared."
  echo ""
  exit 0
fi

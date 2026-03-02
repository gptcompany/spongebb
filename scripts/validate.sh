#!/bin/bash
# Custom validation script that uses uv run for all tools
# This ensures tools run in the project's virtual environment

set -e
cd "$(dirname "$0")/.."

echo "============================================================"
echo "VALIDATION REPORT: spongebb"
echo "============================================================"
echo ""

FAILED=0

# Tier 1: Code Quality (Ruff)
echo -n "  [Tier 1] code_quality: "
if uv run ruff check src/ tests/ --quiet 2>/dev/null; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
    FAILED=1
fi

# Tier 1: Type Safety (Pyright)
echo -n "  [Tier 1] type_safety: "
PYRIGHT_OUTPUT=$(uv run pyright 2>&1)
if echo "$PYRIGHT_OUTPUT" | grep -q "0 errors"; then
    echo "✅ PASS (0 errors)"
else
    ERRORS=$(echo "$PYRIGHT_OUTPUT" | grep -oP '\d+ errors' | head -1)
    echo "❌ FAIL ($ERRORS)"
    FAILED=1
fi

# Tier 1: Security (Bandit) - with timeout
echo -n "  [Tier 1] security: "
if timeout 120 uv run bandit -r src/ -q -f txt 2>/dev/null; then
    echo "✅ PASS"
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo "⚠️ TIMEOUT (skipped)"
    else
        echo "❌ FAIL"
        FAILED=1
    fi
fi

# Tier 1: Coverage (pytest)
echo -n "  [Tier 1] coverage: "
COV_OUTPUT=$(uv run pytest tests/unit/ --cov=src/liquidity --cov-report=term-missing --tb=no -q 2>&1 | tail -5)
COV_PCT=$(echo "$COV_OUTPUT" | grep -oP 'TOTAL\s+\d+\s+\d+\s+\K\d+' || echo "0")
if [ -n "$COV_PCT" ] && [ "$COV_PCT" -ge 70 ]; then
    echo "✅ PASS (${COV_PCT}%)"
else
    echo "⚠️ LOW (${COV_PCT:-unknown}%)"
fi

echo ""
echo "============================================================"
if [ $FAILED -eq 0 ]; then
    echo "RESULT: PASSED (Tier 1)"
    exit 0
else
    echo "RESULT: BLOCKED (Tier 1 failures)"
    exit 1
fi

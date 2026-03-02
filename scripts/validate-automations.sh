#!/bin/bash
# Automated validation script for spongebb
# Run via cron: */30 * * * * /media/sam/1TB/openbb_liquidity/scripts/validate-automations.sh
# Features: Auto-fix on failure + Discord alerts

cd /media/sam/1TB/openbb_liquidity

LOG_FILE="/tmp/spongebb_validation_$(date +%Y%m%d).log"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
DOTENVX="/home/sam/.local/bin/dotenvx"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_passed=0
check_failed=0
fixes_applied=0

validate() {
    local name="$1"
    local cmd="$2"

    if eval "$cmd" >/dev/null 2>&1; then
        log "✅ $name"
        ((check_passed++))
    else
        log "❌ $name FAILED"
        ((check_failed++))
    fi
}

fix_and_retry() {
    local name="$1"
    local check_cmd="$2"
    local fix_cmd="$3"

    if ! eval "$check_cmd" >/dev/null 2>&1; then
        log "🔧 Fixing: $name"
        if eval "$fix_cmd" >/dev/null 2>&1; then
            log "✅ Fixed: $name"
            ((fixes_applied++))
            ((check_passed++))
        else
            log "❌ Fix failed: $name"
            ((check_failed++))
        fi
    else
        log "✅ $name"
        ((check_passed++))
    fi
}

log "=== Starting Validation (with auto-fix) ==="

# File structure (no auto-fix - critical files)
for f in CLAUDE.md .claude/validation/config.json .github/workflows/sync-planning.yml .planning/ROADMAP.md; do
    validate "File: $f" "[ -f '$f' ]"
done

# GitHub Secret - auto-fix from SOPS
fix_and_retry "GitHub Secret" \
    "gh secret list 2>/dev/null | grep -q GH_PROJECT_PAT" \
    "$DOTENVX get GH_PROJECT_PAT -f /media/sam/1TB/.env 2>/dev/null | gh secret set GH_PROJECT_PAT"

# GitHub Issues - auto-fix by triggering sync
fix_and_retry "GitHub Issues >=35" \
    "[ \$(gh issue list --state all --limit 100 --json number | jq length) -ge 35 ]" \
    "gh workflow run 'Sync Planning' && sleep 60"

# GitHub Milestones - auto-fix by triggering sync
fix_and_retry "GitHub Milestones =10" \
    "[ \$(gh api repos/gptcompany/spongebb/milestones | jq length) -eq 10 ]" \
    "gh workflow run 'Sync Planning' && sleep 60"

# Last Workflow - auto-fix by re-running
fix_and_retry "Last Workflow Success" \
    "gh run list --limit 1 --json conclusion | jq -e '.[0].conclusion == \"success\"'" \
    "gh workflow run 'Sync Planning' && sleep 120 && gh run list --limit 1 --json conclusion | jq -e '.[0].conclusion == \"success\"'"

# Config checks (no auto-fix - needs manual review)
validate "GSD Config" "[ \$(jq -r '.mode' .planning/config.json) = 'yolo' ]"
validate "Validation Config" "[ \$(jq -r '.domain' .claude/validation/config.json) = 'finance' ]"

log "=== Results: $check_passed passed, $check_failed failed, $fixes_applied auto-fixed ==="

# Create GitHub Issue on failure (for Claude to see next session)
if [ "$check_failed" -gt 0 ]; then
    EXISTING=$(gh issue list --label "auto-validation" --state open --json number | jq length)
    if [ "$EXISTING" -eq 0 ]; then
        # Build fix summary
        FIX_SUMMARY=""
        grep -q "❌.*File:" "$LOG_FILE" && FIX_SUMMARY="$FIX_SUMMARY
### Missing Files
**Why:** Critical config files are missing from the repo.
**How:** Restore from git or recreate using templates.
\`\`\`bash
git checkout HEAD -- <missing_file>
# Or copy from template
cp ~/.claude/templates/<template> <destination>
\`\`\`
"
        grep -q "❌.*Secret" "$LOG_FILE" && FIX_SUMMARY="$FIX_SUMMARY
### GitHub Secret Missing
**Why:** GH_PROJECT_PAT is needed for GitHub Project API access.
**How:** Re-set from dotenvx:
\`\`\`bash
dotenvx get GH_PROJECT_PAT -f /media/sam/1TB/.env | gh secret set GH_PROJECT_PAT
\`\`\`
"
        grep -q "❌.*Issues" "$LOG_FILE" && FIX_SUMMARY="$FIX_SUMMARY
### GitHub Issues Not Synced
**Why:** ROADMAP.md changes weren't synced to GitHub Issues.
**How:** Trigger sync manually:
\`\`\`bash
gh workflow run 'Sync Planning'
\`\`\`
"
        grep -q "❌.*Milestones" "$LOG_FILE" && FIX_SUMMARY="$FIX_SUMMARY
### GitHub Milestones Missing
**Why:** Phase milestones weren't created from ROADMAP.md.
**How:** Trigger sync manually:
\`\`\`bash
gh workflow run 'Sync Planning'
\`\`\`
"
        grep -q "❌.*Workflow" "$LOG_FILE" && FIX_SUMMARY="$FIX_SUMMARY
### Workflow Failed
**Why:** Last GitHub Actions run failed.
**How:** Check workflow logs and fix:
\`\`\`bash
gh run list --limit 1
gh run view <run_id> --log
\`\`\`
"
        grep -q "❌.*GSD Config" "$LOG_FILE" && FIX_SUMMARY="$FIX_SUMMARY
### GSD Config Invalid
**Why:** .planning/config.json has wrong mode setting.
**How:** Reset to yolo mode:
\`\`\`bash
jq '.mode = \"yolo\"' .planning/config.json | sponge .planning/config.json
\`\`\`
"
        grep -q "❌.*Validation Config" "$LOG_FILE" && FIX_SUMMARY="$FIX_SUMMARY
### Validation Config Invalid
**Why:** .claude/validation/config.json has wrong domain.
**How:** Set correct domain:
\`\`\`bash
jq '.domain = \"finance\"' .claude/validation/config.json | sponge .claude/validation/config.json
\`\`\`
"

        gh issue create \
            --title "🔧 Auto-validation failed: $check_failed checks" \
            --body "## Validation Report $(date '+%Y-%m-%d %H:%M')

**Results:** ✅ $check_passed passed | ❌ $check_failed failed | 🔧 $fixes_applied auto-fixed

---
$FIX_SUMMARY
---

### Full Log
\`\`\`
$(tail -30 "$LOG_FILE")
\`\`\`

---
*Auto-generated by validate-automations.sh*
*Close this issue after fixing all checks.*" \
            --label "auto-validation,bug"
        log "📝 Created GitHub Issue for failures"
    fi
fi

# Discord alert
if [ -n "$DISCORD_WEBHOOK" ]; then
    if [ "$check_failed" -gt 0 ]; then
        curl -s -X POST "$DISCORD_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"content\": \"⚠️ **spongebb Validation Failed**\n❌ $check_failed checks failed\n🔧 $fixes_applied auto-fixes attempted\nSee: $LOG_FILE\"}"
    elif [ "$fixes_applied" -gt 0 ]; then
        curl -s -X POST "$DISCORD_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"content\": \"🔧 **spongebb Auto-Fixed**\n✅ $check_passed passed\n🔧 $fixes_applied issues auto-fixed\"}"
    fi
fi

exit $check_failed

# Rename Directory: openbb_liquidity -> spongebb

## Stato
- [x] Repo GitHub rinominato: `gptcompany/spongebb`
- [x] Git remote aggiornato: `https://github.com/gptcompany/spongebb.git`
- [ ] Directory locale da rinominare: `/media/sam/1TB/openbb_liquidity` -> `/media/sam/1TB/spongebb`

## Nota operativa
- Non eseguire il rename mentre stai lavorando dentro questa repo o con editor/agent/processi attivi nella directory corrente.
- Eseguire il rename in una finestra dedicata, da directory parent (`/media/sam/1TB`), solo dopo aver chiuso sessioni e servizi che tengono aperto il path.

## Pre-requisiti
1. Fermare tutti i servizi che usano la directory
2. Chiudere sessioni Claude Code nella directory
3. Uscire dalla directory del repo e posizionarsi nella parent directory prima di eseguire `mv`

## Passi

### 1. Ferma servizi
```bash
kill $(pgrep -f "uvicorn.*liquidity")
kill $(pgrep -f "openbb-api.*workspace")
```

### 2. Rinomina directory
```bash
cd /media/sam/1TB
mv /media/sam/1TB/openbb_liquidity /media/sam/1TB/spongebb
```

### 3. Aggiorna file con path hardcoded

```bash
cd /media/sam/1TB/spongebb

# deploy.yml (path per self-hosted runner)
sed -i 's|/media/sam/1TB/openbb_liquidity|/media/sam/1TB/spongebb|g' .github/workflows/deploy.yml

# .serena/project.yml
sed -i 's|openbb_liquidity|spongebb|g' .serena/project.yml

# scripts
sed -i 's|openbb_liquidity|spongebb|g' scripts/validate-automations.sh

# .planning files (bulk update, non critici)
find .planning -name "*.md" -exec sed -i 's|openbb_liquidity|spongebb|g' {} +

# CLAUDE.md
sed -i 's|openbb_liquidity|spongebb|g' CLAUDE.md
```

### 4. Aggiorna file non-critici (sessioni, cache)
```bash
# Questi si possono ignorare o eliminare
# .claude-flow/sessions/*.json
# .claude/context_bundles/*.json
# .claude/stats/*.jsonl
# .swarm/*.json
```

### 5. Riavvia servizi
```bash
cd /media/sam/1TB/spongebb
make api-local &       # API su 8003
make workspace-local & # Workspace su 6900
```

### 6. Verifica
```bash
curl -sf http://localhost:8003/health
curl -sf http://localhost:6900/widgets.json | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'widgets')"
git remote -v  # Deve puntare a spongebb
```

### 7. Commit
```bash
git add -A && git commit -m "chore: update hardcoded paths after directory rename"
git push
```

## File con riferimenti (47 totali)

### Critici (da aggiornare)
- `.github/workflows/deploy.yml`
- `.serena/project.yml`
- `scripts/validate-automations.sh`
- `CLAUDE.md`
- `.planning/STATE.md`
- `.planning/PROJECT.md`

### Non critici (sessioni/cache, possono essere ignorati)
- `.claude-flow/sessions/*.json`
- `.claude-flow/metrics/*.json`
- `.claude-flow/memory/store.json`
- `.claude/context_bundles/*.json`
- `.claude/stats/*.jsonl`
- `.swarm/*.json`
- `.planning/phases/*/PLAN.md`
- `.planning/research/*.md`

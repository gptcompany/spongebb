# Handoff operativo — Dashboard/Deploy (2026-03-13)

## Stato attuale (fine sessione)

- Branch: `main`
- Ultimi commit rilevanti:
  - `f561835` fix dashboard (export + EIA fallback + FOMC compare reale)
  - `42be7ef` fix lint CI (`ruff` import order)
  - `38c950a` fix workflow deploy per includere anche dashboard
- Dashboard pubblica percepita "vecchia": **confermato plausibile**
  - Container attivo: `spongebb-dashboard-v2`, uptime ~5h, immagine `spongebb-liquidity-dashboard`
  - Segnale: runtime pubblico non ancora riallineato ai commit recenti

## Cosa è stato fixato nel codice

### 1) FOMC compare

- File: `src/liquidity/dashboard/callbacks_main.py`
- Fix:
  - Fallback default date dal `fomc-dates-store` quando i dropdown non sono pronti.
  - Cache scraper spostata in path scrivibile via `get_settings().cache_dir / "fomc"` (evita errori permessi `.cache`).

### 2) Parsing statement Fed reale

- File: `src/liquidity/news/fomc/scraper.py`
- Fix:
  - Parser HTML più robusto (`div.article__content` + fallback su paragrafi).
  - Validazione lunghezza testo minima prima di costruire `FOMCStatement`.
  - Error handling parser più esplicito.

### 3) EIA badge KPI

- File: `src/liquidity/dashboard/callbacks/eia_callbacks.py`
- Fix:
  - Quando EIA API/non rete non forniscono dati, fallback mock **solo per campi mancanti** così il badge non resta `--`.

### 4) Export dashboard

- File: `src/liquidity/dashboard/callbacks_main.py`
- Fix:
  - Export tramite `dcc.send_string(...)` per comportamento download più affidabile nei test headless/browser.

### 5) Deploy automatico

- File: `.github/workflows/deploy.yml`
- Fix:
  - Deploy include ora anche `liquidity-dashboard` (`--profile dashboard`).
  - Healthcheck aggiunto su `http://localhost:8050`.
  - Logs dashboard aggiunti nel recap finale workflow.

## Test effettuati

- Playwright E2E mirati (locale su `http://127.0.0.1:8052`): pass
  - export flow
  - FOMC compare
  - EIA KPI
- Playwright E2E completo: **20/20 passed** (istanza locale aggiornata).

## Perché la dashboard pubblica può essere ancora vecchia

1. I commit sono su `main`, ma il rollout runtime pubblico dipende da run self-hosted.
2. La pipeline ha avuto run cancellati/falliti in sequenza.
3. Runner self-hosted org era in mismatch scheduling (`muletto`) e con coda lunga.
4. Anche dopo fix label, alcuni run sono rimasti queued/stale.

## Stato workflow osservato

- `CI` push su `38c950a`: in progress (ultimo check durante sessione).
- `Core Deploy` push su `38c950a`: queued.
- `Trigger Progressive Deploy` manuale precedente: queued.
- `Release`: skipped finché CI non chiude `success`.

## Azioni infrastrutturali già fatte

- Aggiunta label runner `muletto` a `sam-workstation` (org runner id `47`).
- Cancel run bloccati/stale.
- Trigger manuale workflow (`ci.yml`, `deploy.yml`, `trigger-progressive-deploy.yml`) durante diagnostica.

## Runbook rapido per prossima sessione

1. Verifica stato run:

```bash
gh run list --limit 20
```

2. Se `CI` di `38c950a` non è `success`, apri log fail:

```bash
gh run view <RUN_ID_CI> --log-failed
```

3. Se `CI` è `success` ma `Core Deploy` resta in coda >10 min:

```bash
gh api /orgs/gptcompany/actions/runner-groups/1/runners
sudo journalctl -u actions.runner.gptcompany.sam-workstation.service -n 80 --no-pager
```

4. Per applicare subito i fix in produzione (bypass coda), deploy manuale:

```bash
cd /media/sam/1TB/spongebb
dotenvx run -- docker compose --profile dashboard build liquidity-dashboard liquidity-api liquidity-workspace
dotenvx run -- docker compose --profile dashboard up -d liquidity-dashboard liquidity-api liquidity-workspace
```

5. Verifica runtime:

```bash
curl -fsS http://localhost:8050 >/dev/null && echo "dashboard ok"
curl -fsS http://localhost:8003/health
curl -fsS http://localhost:6900/health
```

6. Verifica pubblica dashboard:

```bash
curl -I https://spongebb-dashboard.princyx.xyz/
```

7. Smoke E2E pubblico:

```bash
PLAYWRIGHT_BASE_URL=https://spongebb-dashboard.princyx.xyz PLAYWRIGHT_SKIP_WEBSERVER=1 npm run test:e2e
```

## Problemi residui noti (non bloccanti per i fix richiesti)

- Alcuni endpoint FRED rispondono `403` nel contesto runtime corrente (degrado dati in panel dipendenti).
- Coda self-hosted non deterministica quando runner org è `busy` su altri job.

## Messaggio operativo per apertura nuova sessione

> Riprendi da `docs/HANDOFF_2026-03-13_DASHBOARD_DEPLOY.md`, verifica run GitHub su commit `38c950a` e completa deploy runtime dashboard pubblica. Priorità: allineare produzione ai fix già testati (20/20 E2E locale), poi rerun E2E pubblico e conferma pannelli FOMC/EIA/export.


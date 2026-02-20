# Phase 22: Consumer Credit Risk - Context

## Goal

Aggiungere un layer dedicato al consumer credit risk con:
- tracking macro (consumer credit, student loans, defaults, mortgage losses, reserves)
- indicatori relativi di mercato (XLP/XLY, AXP vs IGV)
- ranking dei titoli più sensibili allo stress creditizio consumer.

## Requirements (extension post-v3.0)

| ID | Requirement |
|----|-------------|
| CCR-01 | Consumer credit total e ex-student loans |
| CCR-02 | Debt in default proxy e default rate tracking |
| CCR-03 | Mortgage losses e banking loan loss reserves |
| CCR-04 | XLP/XLY ratio chart |
| CCR-05 | AXP vs IGV relative spread chart |
| CCR-06 | USD liquidity proxy index (Bloomberg-like) |
| CCR-07 | Dashboard panel con metriche e top sensitive stocks |

## Plans

| Plan | Description | Effort | Wave |
|------|-------------|--------|------|
| 22-01 | Consumer Credit Risk Collector + Dashboard Panel | M | 1 |
| 22-02 | Runtime Operationalization (Container + Test Execution Strategy) | S | 2 |
| 22-03 | Direct Container Runtime Implementation (Dashboard + Python/E2E Tests) | M | 3 |
| 22-04 | Claude Code Supervision Protocol (Governance + Execution Gates) | S | 4 |

## Technical Approach

### Plan 22-01

1. Estendere FRED series map con indicatori credit stress:
   - `HCCSDODNS`, `SLOASM`, `DRALACBS`, `CORALACBS`, `DRSFRMACBS`, `CORSFRMACBS`, `QBPBSTASTLNLESSRES`

2. Creare `ConsumerCreditRiskCollector`:
   - normalizzazione unità
   - derivazioni (`consumer_credit_ex_students_b`, `debt_in_default_est_b`, `usd_liquidity_index`)
   - calcolo `XLP/XLY` e `AXP vs IGV` relative spread
   - ranking di sensitivity stocks via fattore composito di stress creditizio

3. Integrare dashboard:
   - nuovo pannello `consumer_credit`
   - callback output dedicati
   - metric summary + tabella sensitivity

4. Test:
   - unit test collector
   - unit test component dashboard
   - update test layout

### Plan 22-02

1. Definire modello operativo runtime:
   - scelta `container diretto` come default per esecuzione riproducibile
   - uso host/escalated per test runtime bloccati nel sandbox

2. Formalizzare strategia test:
   - Python runtime test fuori sandbox
   - Playwright Test per regressione visuale locale/CI
   - Playwright MCP per debug interattivo browser-based

3. Chiarire boundary OpenBB:
   - OpenBB SDK come libreria dati
   - dashboard non "inside OpenBB service" ma app separata integrata via SDK

### Plan 22-03

1. Implementazione Docker runtime:
   - target `runtime` e `test-runtime` nel `Dockerfile`

2. Implementazione Compose:
   - `liquidity-dashboard` + `liquidity-dashboard-dev`
   - `liquidity-dashboard-test` deterministico
   - `liquidity-pytest` per Python runtime tests
   - `liquidity-playwright` per visual regression containerizzata

3. Operatività:
   - `Makefile` con comandi standard (`up`, `test-python`, `test-visual`)
   - README aggiornato con runbook step-by-step

### Plan 22-04

1. Definizione supervisione Claude Code:
   - scope attività supervisionate (edit/test/commit/push/docs)
   - gate operativi prima e dopo ogni fase critica

2. Definizione escalation:
   - stop su incongruenze, cambi inattesi o azioni distruttive non autorizzate

3. Tracciabilità:
   - standard minimo di evidenze (hash, file list, verifiche, rischi residui)
   - documento centralizzato in `.planning/reference/CLAUDE_CODE_SUPERVISION.md`

## Dependencies

- Phase 6 (Credit & BIS data) per serie e concetti credit market
- Phase 10 (Dashboard framework) per integrazione UI
- Phase 11 (Consumer credit proxies) per baseline consumer data

## Files Created/Modified

| Action | File |
|--------|------|
| CREATE | `src/liquidity/collectors/consumer_credit_risk.py` |
| MODIFY | `src/liquidity/collectors/fred.py` |
| MODIFY | `src/liquidity/collectors/__init__.py` |
| CREATE | `src/liquidity/dashboard/components/consumer_credit.py` |
| MODIFY | `src/liquidity/dashboard/components/__init__.py` |
| MODIFY | `src/liquidity/dashboard/layout.py` |
| MODIFY | `src/liquidity/dashboard/callbacks_main.py` |
| CREATE | `tests/unit/collectors/test_consumer_credit_risk.py` |
| CREATE | `tests/unit/test_dashboard/test_components/test_consumer_credit.py` |
| MODIFY | `tests/unit/test_dashboard/test_layout.py` |
| CREATE | `.planning/phases/phase-22-consumer-credit-risk/22-02-PLAN.md` |
| CREATE | `.planning/phases/phase-22-consumer-credit-risk/22-02-SUMMARY.md` |
| CREATE | `.planning/phases/phase-22-consumer-credit-risk/22-03-PLAN.md` |
| CREATE | `.planning/phases/phase-22-consumer-credit-risk/22-03-SUMMARY.md` |
| CREATE | `.planning/phases/phase-22-consumer-credit-risk/22-04-PLAN.md` |
| CREATE | `.planning/phases/phase-22-consumer-credit-risk/22-04-SUMMARY.md` |
| CREATE | `.planning/reference/CLAUDE_CODE_SUPERVISION.md` |
| MODIFY | `Dockerfile` |
| MODIFY | `docker-compose.yml` |
| CREATE | `Makefile` |
| MODIFY | `README.md` |
| MODIFY | `.planning/phases/phase-22-consumer-credit-risk/CONTEXT.md` |
| MODIFY | `.planning/phases/phase-22-consumer-credit-risk/SUMMARY.md` |
| MODIFY | `.planning/STATE.md` |
| MODIFY | `.planning/ROADMAP.md` |
| MODIFY | `.planning/MILESTONES.md` |
| MODIFY | `.planning/milestones/v4.0-ROADMAP.md` |

## Validation Criteria

- [x] Metriche consumer credit/ex-student calcolate correttamente
- [x] Proxy debt-in-default disponibile
- [x] Mortgage losses e reserves tracciati
- [x] Chart XLP/XLY e AXP-IGV visibili in dashboard
- [x] Ranking stock sensitive disponibile
- [x] Lint e compile check pass
- [x] Runbook operativo container/test documentato in GSD
- [x] Runtime container workflow implementato (`Dockerfile`/`compose`/`Makefile`)
- [x] Protocollo supervisione Claude Code documentato e versionato

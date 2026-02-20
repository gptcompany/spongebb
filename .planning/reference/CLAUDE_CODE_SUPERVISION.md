# Claude Code Supervision Protocol

**Version:** 1.0  
**Status:** Active  
**Updated:** 2026-02-20

## Purpose

Definire un protocollo standard di supervisione per attività svolte con Claude Code/Codex nella repo, mantenendo controllo su qualità, rischio e tracciabilità.

## Supervision Scope

Il protocollo si applica a:
- modifiche codice e configurazione
- test runtime (Python/E2E/visual)
- commit e push
- aggiornamenti documentazione GSD

## Execution Gates

### Gate 1: Pre-Edit

Verifiche obbligatorie:
- obiettivo e scope espliciti
- file target identificati
- rischi noti (regressioni, dipendenze, side effect) dichiarati

Output minimo:
- breve piano operativo

### Gate 2: Pre-Commit

Verifiche obbligatorie:
- review diff sui file toccati
- conferma che non ci siano cambiamenti non correlati nello stage
- evidenza validazione minima (lint/compile/config checks o motivazione se non eseguibili)

Output minimo:
- changelog sintetico per file

### Gate 3: Pre-Push

Verifiche obbligatorie:
- commit message coerente con contenuto
- branch target corretto
- rischi residui esplicitati

Output minimo:
- dichiarazione pronta al push + eventuali limitazioni

### Gate 4: Post-Push

Verifiche obbligatorie:
- hash commit finali
- elenco file aggiornati
- sync stato GSD (phase/context/summary/state/roadmap/milestones)

Output minimo:
- runbook di cross-check per l’utente

## Escalation Rules

Stop immediato e richiesta decisione utente quando:
- emergono modifiche inattese nel worktree non riconducibili al task corrente
- i risultati test/documentazione sono incoerenti con l’implementazione
- è richiesta un’azione potenzialmente distruttiva non esplicitamente autorizzata
- la validazione runtime è bloccata dall’ambiente e non c’è fallback operativo chiaro

## Traceability Standard

Ogni attività supervisionata deve lasciare:
- commit atomici e descrittivi
- riferimenti commit nei file GSD milestone/summary
- note su vincoli ambiente (es. sandbox runtime limits)
- comandi ripetibili per verifica locale/host

## Review Cadence

- ad ogni cambiamento sostanziale: review immediata (in-session)
- a fine blocco implementativo: review completa pre-push
- post-push: verifica integrità documentazione GSD

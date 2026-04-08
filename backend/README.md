# PunkAgent

CLI e API per gestire movimenti bancari, analisi spese e insight su obiettivi finanziari con un agente DeepAgents basato su `gpt-5.4`.

## Cosa fa

PunkAgent e' ottimizzato per:

- analisi di spesa per categoria
- analisi di una settimana specifica, con default sulla settimana corrente
- analisi di un mese specifico, con default sul mese corrente
- analisi dell'intero storico disponibile
- calcolo delle spese fisse mensili a partire da `macrocategoria = Spese Fisse`
- insight settimanali e mensili guidati dall'obiettivo utente
- consulenza pratica per migliorare la gestione delle finanze personali in base a profilo e comportamento di spesa
- ingestione di movimenti da estratti conto PDF, foto di scontrini e testo libero

## Architettura agente

- root agent: gestisce chat, allegati, persistenza su DB, aggiornamento profilo e registrazione movimenti
- subagent `category-analyst`: analisi per categoria, ricorrenze e voci da rivedere
- subagent `period-analyst`: analisi per settimana, mese e intero storico
- subagent `goal-insights-analyst`: insight settimanali e mensili in funzione dell'obiettivo utente
- skills locali in `src/punkathon_agent/skills/project/`: una per categoria, settimana, mese, storico, spese fisse, goal insight, coaching finanziario e ingestione movimenti

Gli allegati PDF e immagini restano nel root agent: i subagent lavorano solo su contesto testuale e tool di analisi.

## Layout package

Il package e' stato riordinato cosi':

- `src/punkathon_agent/cli/`: CLI Typer e API FastAPI
- `src/punkathon_agent/db/`: engine, sessioni, path DB e migrazioni leggere
- `src/punkathon_agent/models/`: modelli Pydantic, SQLModel e tipi di dominio
- `src/punkathon_agent/services/`: classificazione movimenti e logica di analisi
- `src/punkathon_agent/punkagent/`: runtime agente, prompt, attachment handling e tool

Restano shim di compatibilita' per i vecchi import path principali.

## Tool principali

- `aggiungi_movimenti`
- `analizza_spese_per_categoria`
- `analizza_spese_settimana`
- `analizza_spese_mese`
- `analizza_spese_complessive`
- `calcola_spese_fisse_mensili`
- `genera_insight_settimanali`
- `genera_insight_mensili`

Sono ancora disponibili i tool storici come `analizza_budget_attuale` e `analizza_spesa_categorie`, ma ora fanno da bridge verso le API di dominio nuove.

## CLI unificata

Tutte le operazioni passano da un solo comando: `punkagent`.

## Avvio chat

```bash
uv run punkagent chat
```

La chat streamma reasoning e risposta finale in tempo reale.

Per comodita', `uv run punkagent` senza sottocomandi continua ad avviare direttamente la chat.

## Ricostruzione database

```bash
uv run punkagent rebuild-db
```

Per saltare la conferma:

```bash
uv run punkagent rebuild-db --force
```

## Grafo LangGraph

```bash
uv run punkagent graph
```

Per default salva il Mermaid in `docs/punkagent-langgraph.mmd`.

## API FastAPI

```bash
uv run punkagent api
```

Endpoint:

- `GET /health`
- `POST /chat`
- `POST /chat/stream`

## Profilo utente

La tabella `utente` contiene:

- `stipendio_mensile`
- `spese_fisse_essenziali_mensili`
- `disponibile_mensile`
- `disponibile_settimanale`
- `obiettivo`
- `spese_irrinunciabili`
- `risparmio` interno write-only

Se manca lo stipendio e serve per budget o insight, l'agente lo chiede. Le spese fisse essenziali vengono invece stimate automaticamente quando possibile.
Quando l'utente chiede genericamente `spese fisse`, l'agente deve usare sempre il totale da `macrocategoria = Spese Fisse`; il campo profilo `spese_fisse_essenziali_mensili` va usato solo per budget e goal.

## Esempi utili

```text
/attach data/operazioni_1.pdf
importa i movimenti da questo estratto conto

/attach data/foto_1.jpeg
salva questo scontrino

quanto ho speso in ristoranti questo mese?

fammi l'analisi della settimana

analizza marzo 2026

dammi un quadro generale di tutto lo storico

calcola le mie spese fisse mensili

prendo 2400 euro al mese e il mio obiettivo e' mettere via 400 euro al mese
fammi insight mensili sul mio andamento

come posso gestire meglio le mie finanze in base a come sto spendendo?

aiutami a capire dove tagliare per risparmiare 200 euro al mese
```

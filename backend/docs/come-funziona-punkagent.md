# Come Funziona PunkAgent

## Obiettivo del progetto

PunkAgent e' un agente che lavora su un database locale di movimenti bancari e un profilo utente persistente. Il flusso e' stato ripulito per concentrare il prodotto su otto casi d'uso:

1. analisi di spesa per categoria
2. analisi di una settimana specifica, con default sulla settimana corrente
3. analisi di un mese specifico, con default sul mese corrente
4. analisi completa su tutto il dataset
5. calcolo delle spese fisse mensili via macrocategoria
6. insight settimanali e mensili basati sull'obiettivo utente
7. consulenza pratica sulla gestione delle finanze personali basata su profilo e comportamento di spesa
8. aggiunta di movimenti da PDF, scontrini o testo libero

## Struttura del package

- `src/punkathon_agent/cli/`
  - `app.py`: CLI Typer
  - `api.py`: API FastAPI
- `src/punkathon_agent/db/`
  - `core.py`: engine SQLite, sessioni e migrazioni leggere
- `src/punkathon_agent/models/`
  - `agent.py`: payload e richieste dei tool
  - `db.py`: modelli SQLModel
  - `finance.py`: enum e modelli di classificazione
  - `api.py`: request/response della API
- `src/punkathon_agent/services/`
  - `classification.py`: classificazione AI e rule-based dei movimenti
  - `spending.py`: logica di analisi, budget, periodi e serializzazione
- `src/punkathon_agent/punkagent/`
  - `runtime.py`: runtime DeepAgents
  - `prompts.py`: prompt di root agent e subagent
  - `tools.py`: tool pubblici esposti all'agente
  - `attachments.py`: gestione file allegati

I vecchi moduli flat top-level restano dove serve come shim di compatibilita'.

## Runtime agente

### Root agent

Il root agent:

- riceve il messaggio utente
- inietta il contesto del profilo dal database
- legge allegati PDF o immagini
- salva movimenti e aggiorna profilo
- decide se usare direttamente un tool o delegare a un subagent

### Subagent

I subagent attuali sono:

- `category-analyst`
  - usa i tool di categoria e di spese fisse
  - serve per ricorrenze, abbonamenti, tagli e breakdown categoria
- `period-analyst`
  - usa i tool di settimana, mese e storico
  - serve per review di periodo e confronti con lo storico
- `goal-insights-analyst`
  - usa i tool di insight settimanali e mensili
  - serve per capire se l'utente e' in linea con il proprio obiettivo

## Tool di dominio

I tool principali sono:

- `aggiungi_movimenti`
- `analizza_spese_per_categoria`
- `analizza_spese_settimana`
- `analizza_spese_mese`
- `analizza_spese_complessive`
- `calcola_spese_fisse_mensili`
- `genera_insight_settimanali`
- `genera_insight_mensili`

Tool storici ancora disponibili per compatibilita':

- `analizza_budget_attuale`
- `analizza_spesa_categorie`
- `ottieni_movimenti_mese_corrente`
- `costruisci_query_sql`
- `esegui_query_sql`

## Skills

Le skill locali attive sono:

- `category-spending-analysis`
- `weekly-spending-analysis`
- `monthly-spending-analysis`
- `overall-spending-analysis`
- `fixed-expense-analysis`
- `goal-insights`
- `personal-finance-coach`
- `movement-ingestion`

Ogni skill e' focalizzata su un singolo dominio operativo invece che su flussi troppo generici.

## Profilo utente

La tabella `utente` contiene:

- stipendio mensile
- spese fisse essenziali mensili
- disponibile mensile
- disponibile settimanale
- obiettivo
- spese irrinunciabili
- risparmio interno write-only

Il budget disponibile deriva da stipendio e spese fisse essenziali. Il tool `calcola_spese_fisse_mensili` invece produce una vista diversa: stima le spese fisse mensili dalla `macrocategoria`, quindi puo' includere anche voci fisse non necessariamente essenziali.
Nelle risposte utente, la formula `spese fisse` va quindi riservata al totale da macrocategoria; il valore nel profilo va chiamato sempre `spese fisse essenziali`.

## Ingestione movimenti

### Estratti conto PDF

Il root agent legge il PDF, estrae i movimenti affidabili e li salva con `aggiungi_movimenti`.

### Scontrini e ricevute

Il root agent salva una spesa negativa con dettagli utili nelle note.

### Testo libero

Se l'utente scrive movimenti in linguaggio naturale, il root agent li struttura e li salva con `aggiungi_movimenti`.

## Verifica minima consigliata

Quando tocchi il progetto:

1. compila il package con `python3 -m compileall src`
2. fai smoke test sugli import pubblici
3. prova almeno i tool di settimana, mese, storico e spese fisse su database vuoto o di esempio

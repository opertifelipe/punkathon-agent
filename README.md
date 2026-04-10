# PunkAgent

Agente AI per gestione movimenti bancari, analisi spese e coaching finanziario personale.

## Prerequisiti

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 18+
- npm

## Configurazione variabili d'ambiente

Crea il file `backend/.env`:

```env
OPENAI_API_KEY=sk-...
```

## Backend

```bash
cd backend
uv run punkagent api
```

Il server parte su `http://localhost:8000`.

### Altri comandi utili

```bash
# Chat da terminale
uv run punkagent chat

# Ricostruzione database
uv run punkagent rebuild-db

# Grafo LangGraph
uv run punkagent graph
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Il dev server parte su `http://localhost:5173` e proxya `/api` verso il backend su `http://localhost:8000`.

## Avvio completo (due terminali)

**Terminale 1 — backend:**
```bash
cd backend && uv run punkagent api
```

**Terminale 2 — frontend:**
```bash
cd frontend && npm run dev
```

Poi apri `http://localhost:5173`.

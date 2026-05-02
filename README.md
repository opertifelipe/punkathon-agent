# Aurora

Aurora is a full-stack application for managing personal bank transactions, importing statements and receipts, analyzing spending, and receiving financial coaching through an AI agent.

The project combines:

- a Python/FastAPI backend with a local SQLite database;
- a DeepAgents/LangGraph agent powered by OpenAI models;
- a Typer CLI for terminal chat, database maintenance, and graph generation;
- a React/Vite frontend for the dashboard, chat, transaction history, insights, and user profile.

Some internal package names, commands, and environment variables still use `punkagent` or `PUNKAGENT` for compatibility with the current codebase.

## Purpose

Aurora turns raw banking data into a useful and queryable personal finance view. Users can:

- upload bank statement PDFs, receipts, and expense images;
- add transactions from natural language;
- browse and correct their transaction history;
- classify expenses by category and macro-category;
- analyze weekly, monthly, or full-history spending;
- estimate fixed expenses and remaining budget;
- configure salary and financial goals;
- receive AI-generated insights based on spending behavior;
- ask for practical advice about saving, recurring costs, subscriptions, and priorities.

The database is local, so the project is designed for development, demos, and prototyping a personal finance assistant.

## Core Features

### Transaction Import

Aurora can import transactions from:

- bank statement PDFs;
- receipt or expense images;
- free-form text written in chat.

During import, the system tries to extract the transaction date, description, amount, category, macro-category, and notes. PDFs are handled by the dedicated flow in `statement_pdf_import.py`; images and free-form text go through the agent runtime.

### Spending Analysis

The agent exposes domain tools for:

- category-level analysis;
- current-week or specific-week analysis;
- current-month or specific-month analysis;
- full-history analysis;
- monthly fixed expense calculation;
- weekly remaining budget calculation;
- weekly and monthly insight generation.

### User Profile and Budget

Each user has a persistent financial profile with:

- monthly salary;
- monthly essential fixed expenses;
- monthly available budget;
- weekly available budget;
- financial goal;
- non-negotiable expenses;
- internal savings value.

The available budget is derived from salary and essential fixed expenses. The "monthly fixed expenses" shown in spending analyses are calculated from transactions classified as `Spese Fisse`.

### Chat and Financial Coaching

The chat supports questions such as:

```text
How much did I spend in restaurants this month?
Analyze the current week.
Which subscriptions can I cut?
Import this bank statement.
I want to save 400 euros per month. Am I on track?
```

The runtime uses a root agent that can read attachments, update the database, call domain tools, and delegate focused analysis to specialized subagents.

### Web Dashboard

The frontend includes:

- authentication and user sessions;
- weekly spending overview;
- insight panels;
- streaming chat;
- profile management;
- transaction history with year, month, and week filters;
- transaction creation, editing, and deletion.

## Architecture

```text
punkathon-agent/
├── backend/
│   ├── src/punkathon_agent/
│   │   ├── cli/              # Typer CLI and FastAPI app
│   │   ├── db/               # SQLite engine, sessions, and lightweight migrations
│   │   ├── models/           # SQLModel, Pydantic, and domain types
│   │   ├── punkagent/        # Agent runtime, prompts, tools, and attachments
│   │   ├── services/         # Spending analysis, classification, PDF import, insights
│   │   ├── auth.py           # JWT, password hashing, and authentication
│   │   └── ...
│   ├── docs/                 # Technical documentation and LangGraph artifacts
│   ├── tests/                # Backend tests
│   ├── db/                   # Generated local SQLite database
│   └── pyproject.toml
├── frontend/
│   ├── src/app/
│   │   ├── api/              # HTTP client for /api
│   │   ├── components/       # React application components
│   │   └── App.tsx
│   ├── src/styles/           # CSS, Tailwind, and theme files
│   ├── public/
│   └── package.json
├── data/                     # Example files for import flows
├── images/                   # Image assets
├── pyproject.toml            # uv workspace
└── README.md
```

## Backend

The backend is a Python package managed with `uv`. The main modules are:

- `punkathon_agent.cli.app`: the `punkagent` command, CLI chat, graph generation, and database rebuild command;
- `punkathon_agent.cli.api`: the FastAPI app and HTTP endpoints;
- `punkathon_agent.db.core`: database creation, SQLite path handling, sessions, and lightweight migrations;
- `punkathon_agent.models.db`: the `punk_users`, `movimenti_bancari`, and `utente` tables;
- `punkathon_agent.punkagent.runtime`: deep agent construction, streaming, and conversation serialization;
- `punkathon_agent.punkagent.tools`: tools available to the agent;
- `punkathon_agent.services.spending`: financial analysis logic;
- `punkathon_agent.services.classification`: AI and rule-based transaction classification;
- `punkathon_agent.services.statement_pdf_import`: automatic import from bank statement PDFs;
- `punkathon_agent.services.ai_insights`: goal-based sidebar insights;
- `punkathon_agent.services.insight_tts`: text-to-speech generation for insights.

### Database

The default database path is:

```text
backend/db/movimenti_bancari.sqlite3
```

The main tables are:

- `punk_users`: application users;
- `movimenti_bancari`: user transactions, including date, description, amount, category, and macro-category;
- `utente`: the user's financial profile.

The database is created automatically whenever the backend opens a session.

## Agent Runtime

The root agent:

- receives user messages from the CLI or API;
- reads frontend context when available;
- tracks the current user through context variables;
- imports attachments;
- calls analysis and persistence tools;
- updates the user profile;
- delegates specific analysis tasks to subagents.

The main subagents are:

- `category-analyst`: categories, recurring expenses, subscriptions, and fixed expenses;
- `period-analyst`: weekly, monthly, historical, and comparative analysis;
- `goal-insights-analyst`: insights related to the user's financial goal.

Project-specific skills live in:

```text
backend/src/punkathon_agent/skills/project/
```

## Main API Endpoints

The backend exposes a FastAPI application. The most relevant endpoints are:

- `GET /health`
- `POST /auth/signup`
- `POST /auth/signin`
- `GET /auth/me`
- `POST /chat`
- `POST /chat/stream`
- `GET /utente`
- `PATCH /utente`
- `GET /spese-settimanali`
- `GET /estratto-conto`
- `POST /estratto-conto/movimenti`
- `PUT /estratto-conto/movimenti/{movement_id}`
- `DELETE /estratto-conto/movimenti/{movement_id}`
- `DELETE /estratto-conto/movimenti`
- `GET /insights/status`
- `POST /insights/generate`
- `POST /insights/generate-one`
- `POST /insights/text-to-speech`

The frontend calls the backend through the `/api` prefix, which Vite proxies to the local backend server.

## Requirements

- Python 3.12+
- `uv`
- Node.js 18+
- npm
- a valid OpenAI API key

## Configuration

Create `backend/.env`:

```env
OPENAI_API_KEY=sk-...
```

Optional variables:

```env
DATABASE_URL=sqlite:///backend/db/movimenti_bancari.sqlite3
PUNKAGENT_AUTH_SECRET=<long-random-secret>
PUNKAGENT_ALLOWED_EMAILS=operti.felipe@proton.me
PUNKAGENT_API_HOST=127.0.0.1
PUNKAGENT_API_PORT=8000
PUNKAGENT_FRONTEND_DIST=/app/frontend/dist
OPENAI_USE_RESPONSES_API=true
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=...
AZURE_DOCUMENT_INTELLIGENCE_KEY=...
```

`PUNKAGENT_AUTH_SECRET` is required for authentication. Generate a long random value for every deployed environment.
`DATABASE_URL` defaults to the local SQLite database. For Azure SQL, use a SQLAlchemy URL such as `mssql+pyodbc://...?...driver=ODBC+Driver+18+for+SQL+Server`.
`PUNKAGENT_ALLOWED_EMAILS` is a comma-separated allowlist for signup and signin; the production container defaults to `operti.felipe@proton.me`.

## Installation

From the repository root:

```bash
uv sync
```

For the frontend:

```bash
cd frontend
npm install
```

## Development

### Backend

```bash
cd backend
uv run punkagent api
```

The API starts at:

```text
http://127.0.0.1:8000
```

### Frontend

In a second terminal:

```bash
cd frontend
npm run dev
```

The development server starts at:

```text
http://localhost:5173
```

Vite forwards `/api` requests to the local backend.

## CLI

### Terminal Chat

```bash
cd backend
uv run punkagent chat
```

Or:

```bash
cd backend
uv run punkagent
```

The CLI supports attachments:

```text
/attach data/operazioni_1.pdf
/attachments
/clear
```

### Rebuild the Database

```bash
cd backend
uv run punkagent rebuild-db
```

Skip confirmation:

```bash
cd backend
uv run punkagent rebuild-db --force
```

### Generate the LangGraph Graph

```bash
cd backend
uv run punkagent graph
```

Available formats:

```bash
uv run punkagent graph --format mermaid
uv run punkagent graph --format ascii --stdout
uv run punkagent graph --format png
```

## Tests and Checks

From the backend:

```bash
cd backend
uv run pytest
```

Quick Python import check:

```bash
cd backend
uv run python -m compileall src
```

Frontend build:

```bash
cd frontend
npm run build
```

## Container Build

The root `Dockerfile` builds the React frontend, installs the FastAPI backend, includes the Microsoft ODBC Driver 18 needed by Azure SQL, and serves the frontend from the same container.

Build locally:

```bash
docker build -t aurora:local .
```

At runtime, configure at least:

```env
OPENAI_API_KEY=sk-...
PUNKAGENT_AUTH_SECRET=<long-random-secret>
DATABASE_URL=<azure-sql-sqlalchemy-url>
PUNKAGENT_ALLOWED_EMAILS=operti.felipe@proton.me
```

## Example Prompts

Examples for the chat:

```text
Import the transactions from this bank statement.
How much did I spend this week?
Analyze March 2026.
Show me my monthly fixed expenses.
Which categories weigh the most on my budget?
I have a salary of 2400 euros and I want to save 400 euros per month.
Generate monthly insights about my progress.
How can I reduce variable expenses by 200 euros per month?
```

## Project Notes

The repository also contains example files in `data/`, images in `images/`, technical documentation in `backend/docs/`, and experimental notebooks in `backend/notebooks/`.

Some top-level backend modules remain as compatibility shims for older import paths. New changes should target the main structure under `backend/src/punkathon_agent/`.

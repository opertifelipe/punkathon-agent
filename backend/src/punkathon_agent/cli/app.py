from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
import shlex
import sys
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH)

from punkathon_agent.db import DB_PATH, get_session, rebuild_database
from punkathon_agent.punkagent import (
    get_punk_agent,
    resolve_attachment_path,
    run_agent_turn_streaming,
    supported_attachment_formats,
)
from punkathon_agent.services.users import resolve_default_cli_user

app = typer.Typer(
    add_completion=False,
    help="CLI unificata per chat, API, database e strumenti di Aurora.",
)

EXIT_COMMANDS = {"exit", "quit", "q", "/exit"}
ATTACH_COMMANDS = {"/attach", "/allega"}
LIST_ATTACHMENTS_COMMANDS = {"/attachments", "/files"}
CLEAR_ATTACHMENTS_COMMANDS = {"/clear", "/clear-attachments"}
HELP_COMMANDS = {"/help", "/?"}
REASONING_COLOR = typer.colors.BLUE
ANSWER_COLOR = typer.colors.GREEN
CLI_COMMANDS = {"api", "chat", "create-db", "graph", "rebuild-db"}


class GraphFormat(StrEnum):
    ASCII = "ascii"
    MERMAID = "mermaid"
    PNG = "png"


@dataclass(frozen=True, slots=True)
class CliDefaultContext:
    user_id: int
    frontend_context: dict[str, Any] | None = None


def _default_graph_output_path(graph_format: GraphFormat) -> Path:
    suffix_by_format = {
        GraphFormat.ASCII: ".txt",
        GraphFormat.MERMAID: ".mmd",
        GraphFormat.PNG: ".png",
    }
    return PROJECT_ROOT / "docs" / f"aurora-langgraph{suffix_by_format[graph_format]}"


def _print_attachment_help() -> None:
    typer.echo("Comandi allegati: /attach <file>, /attachments, /clear")
    typer.echo(f"Formati supportati: {supported_attachment_formats()}")


def _format_attachment_queue(attachments: list[Path]) -> str:
    return ", ".join(str(path) for path in attachments)


def _handle_chat_command(user_input: str, queued_attachments: list[Path]) -> tuple[bool, list[Path]]:
    command, _, remainder = user_input.partition(" ")
    normalized_command = command.lower()

    if normalized_command in HELP_COMMANDS:
        _print_attachment_help()
        return True, queued_attachments

    if normalized_command in LIST_ATTACHMENTS_COMMANDS:
        if queued_attachments:
            typer.echo(f"Allegati in coda: {_format_attachment_queue(queued_attachments)}")
        else:
            typer.echo("Nessun allegato in coda.")
        return True, queued_attachments

    if normalized_command in CLEAR_ATTACHMENTS_COMMANDS:
        if queued_attachments:
            typer.echo("Coda allegati svuotata.")
        else:
            typer.echo("Non ci sono allegati da rimuovere.")
        return True, []

    if normalized_command in ATTACH_COMMANDS:
        if not remainder.strip():
            typer.secho("Specifica almeno un percorso file dopo /attach.", fg=typer.colors.YELLOW)
            return True, queued_attachments

        try:
            raw_paths = shlex.split(remainder)
        except ValueError as exc:
            typer.secho(f"Sintassi allegato non valida: {exc}", fg=typer.colors.RED)
            return True, queued_attachments

        try:
            resolved_paths = [resolve_attachment_path(raw_path) for raw_path in raw_paths]
        except ValueError as exc:
            typer.secho(str(exc), fg=typer.colors.RED)
            return True, queued_attachments

        next_queue = queued_attachments.copy()
        for path in resolved_paths:
            if path not in next_queue:
                next_queue.append(path)

        typer.echo(f"Allegati in coda per il prossimo messaggio: {_format_attachment_queue(next_queue)}")
        return True, next_queue

    return False, queued_attachments


def _print_welcome() -> None:
    typer.echo("Aurora avviata. Scrivi una richiesta su spese, movimenti e insight settimanali o mensili.")
    typer.echo("Comandi di uscita: exit, quit, q, /exit")
    _print_attachment_help()


async def _stream_cli_turn(
    agent: Any,
    conversation: list[Any],
    user_input: str,
    queued_attachments: list[Path],
    *,
    user_id: int,
    frontend_context: dict[str, Any] | None = None,
) -> tuple[str, list[Any]]:
    current_section: str | None = None
    saw_answer = False

    async def on_event(event: dict[str, str]) -> None:
        nonlocal current_section, saw_answer

        event_type = event.get("type")
        content = event.get("content", "")
        if event_type not in {"reasoning", "answer"} or not content:
            return

        if current_section != event_type:
            if current_section is not None:
                typer.echo()

            label = "thinking: " if event_type == "reasoning" else "agent: "
            color = REASONING_COLOR if event_type == "reasoning" else ANSWER_COLOR
            typer.secho(label, fg=color, nl=False)
            current_section = event_type

        if event_type == "answer":
            saw_answer = True

        color = REASONING_COLOR if event_type == "reasoning" else ANSWER_COLOR
        typer.secho(content, fg=color, nl=False)

    answer, next_conversation, _reload = await run_agent_turn_streaming(
        agent,
        conversation,
        user_input,
        attachment_paths=queued_attachments,
        frontend_context=frontend_context,
        user_id=user_id,
        on_event=on_event,
    )

    if current_section is not None:
        typer.echo()

    if not saw_answer:
        typer.secho(f"agent: {answer}", fg=ANSWER_COLOR)

    return answer, next_conversation


@app.command()
def chat(
    prompt: str | None = typer.Argument(default=None, help="Messaggio iniziale opzionale."),
) -> None:
    """Avvia una chat terminale con Aurora collegata al database SQLite."""
    _run_chat_session(prompt)


@app.command()
def api() -> None:
    """Avvia la API FastAPI di Aurora."""
    from .api import main as api_main

    api_main()


def _resolve_default_cli_context() -> CliDefaultContext:
    with get_session() as session:
        user = resolve_default_cli_user(session)

    if user.id is None:
        raise RuntimeError("Utente CLI senza identificatore persistito.")

    return CliDefaultContext(user_id=user.id)


def _run_chat_session(prompt: str | None = None) -> None:
    cli_context = _resolve_default_cli_context()
    agent = get_punk_agent()
    conversation: list[Any] = []
    queued_attachments: list[Path] = []
    pending_prompt = prompt

    _print_welcome()

    while True:
        try:
            if pending_prompt is None:
                user_input = typer.prompt("tu")
            else:
                user_input = pending_prompt
                typer.echo(f"tu: {user_input}")
                pending_prompt = None
        except (EOFError, KeyboardInterrupt):
            typer.echo("\nChiusura chat.")
            raise typer.Exit(code=0)

        normalized_input = user_input.strip()
        if not normalized_input:
            continue
        if normalized_input.lower() in EXIT_COMMANDS:
            typer.echo("Chiusura chat.")
            raise typer.Exit(code=0)

        handled, queued_attachments = _handle_chat_command(normalized_input, queued_attachments)
        if handled:
            continue

        try:
            _answer, conversation = asyncio.run(
                _stream_cli_turn(
                    agent,
                    conversation,
                    normalized_input,
                    queued_attachments,
                    user_id=cli_context.user_id,
                    frontend_context=cli_context.frontend_context,
                )
            )
        except Exception as exc:
            typer.secho(f"Errore durante l'esecuzione dell'agente: {exc}", fg=typer.colors.RED)
            continue

        queued_attachments = []


def _build_graph_artifact(graph_format: GraphFormat, output_path: Path | None, stdout: bool) -> str | Path:
    if graph_format == GraphFormat.PNG and stdout:
        raise typer.BadParameter("--stdout non e' supportato con --format png.")

    graph = get_punk_agent().get_graph()

    if graph_format == GraphFormat.ASCII:
        artifact = graph.draw_ascii()
        if stdout:
            return artifact

        destination = output_path or _default_graph_output_path(graph_format)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"{artifact}\n", encoding="utf-8")
        return destination

    if graph_format == GraphFormat.MERMAID:
        artifact = graph.draw_mermaid()
        if stdout:
            return artifact

        destination = output_path or _default_graph_output_path(graph_format)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"{artifact}\n", encoding="utf-8")
        return destination

    destination = output_path or _default_graph_output_path(graph_format)
    destination.parent.mkdir(parents=True, exist_ok=True)
    graph.draw_mermaid_png(output_file_path=str(destination))
    return destination


@app.command()
def graph(
    format: GraphFormat = typer.Option(
        GraphFormat.MERMAID,
        "--format",
        "-f",
        case_sensitive=False,
        help="Formato del grafo da generare: ascii, mermaid o png.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Percorso file di output. Se omesso usa docs/aurora-langgraph.<estensione>.",
    ),
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Stampa il grafo su stdout invece di salvarlo su file. Disponibile per ascii e mermaid.",
    ),
) -> None:
    """Genera il grafo LangGraph di Aurora usando i renderer nativi di LangGraph."""
    artifact = _build_graph_artifact(format, output, stdout)

    if stdout:
        typer.echo(str(artifact))
        return

    typer.echo(f"Grafo LangGraph salvato in: {artifact}")


@app.command("create-db")
def create_db() -> None:
    """Cancella e ricrea le tabelle del database configurato."""
    from sqlalchemy.engine import make_url

    from punkathon_agent.db import DATABASE_URL, recreate_database

    try:
        recreate_database()
    except Exception as exc:
        typer.secho(f"Errore durante la ricreazione del database: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    database_target = make_url(DATABASE_URL).render_as_string(hide_password=True)
    typer.echo(f"Tabelle database cancellate e ricreate in: {database_target}")


@app.command("rebuild-db")
def rebuild_db(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Salta la conferma ed elimina il database prima di ricrearlo.",
    ),
) -> None:
    """Elimina il database SQLite e lo ricrea da zero."""
    if not force and not typer.confirm(f"Eliminare e ricreare il database in {DB_PATH}?"):
        typer.echo("Operazione annullata.")
        raise typer.Exit(code=0)

    try:
        rebuilt_path = rebuild_database()
    except OSError as exc:
        typer.secho(f"Errore durante la ricostruzione del database: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Database ricreato in: {rebuilt_path}")


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        sys.argv = [sys.argv[0], "chat"]
    elif argv[0] not in CLI_COMMANDS and not argv[0].startswith("-"):
        sys.argv = [sys.argv[0], "chat", *argv]

    app()


if __name__ == "__main__":
    main()

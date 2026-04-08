from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .constants import SUPPORTED_ATTACHMENT_MIME_TYPES
from .schemas import MessageContent


def supported_attachment_formats() -> str:
    return ".pdf, .png, .jpg, .jpeg, .webp, .gif"


def _encode_file_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _guess_mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def resolve_attachment_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = (Path.cwd() / resolved).resolve()
    else:
        resolved = resolved.resolve()

    if not resolved.exists():
        raise ValueError(f"File non trovato: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"Il percorso non punta a un file: {resolved}")

    mime_type = _guess_mime_type(resolved)
    if mime_type not in SUPPORTED_ATTACHMENT_MIME_TYPES:
        raise ValueError(
            f"Formato non supportato per l'allegato: {resolved.name}. Supportati: {supported_attachment_formats()}."
        )

    return resolved


def _build_attachment_block(path: Path) -> dict[str, Any]:
    mime_type = _guess_mime_type(path)
    base64_payload = _encode_file_to_base64(path)

    return _build_attachment_block_from_payload(
        filename=path.name,
        mime_type=mime_type,
        base64_payload=base64_payload,
    )


def _build_attachment_block_from_payload(
    *,
    filename: str,
    mime_type: str,
    base64_payload: str,
) -> dict[str, Any]:
    if mime_type not in SUPPORTED_ATTACHMENT_MIME_TYPES:
        raise ValueError(f"Formato allegato non supportato: {filename}")

    if mime_type == "application/pdf":
        return {
            "type": "file",
            "file": {
                "file_data": f"data:{mime_type};base64,{base64_payload}",
                "filename": filename,
            },
        }

    if mime_type.startswith("image/"):
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{base64_payload}",
                "detail": "auto",
            },
        }

    raise ValueError(f"Formato allegato non supportato: {filename}")


def build_user_message_content(
    user_input: str,
    attachment_paths: list[str | Path] | None = None,
    inline_attachments: list[dict[str, str]] | None = None,
    frontend_context: dict[str, Any] | None = None,
) -> MessageContent:
    cleaned_input = user_input.strip() or "Analizza gli allegati e procedi con la richiesta dell'utente."
    frontend_context_text = _format_frontend_context(frontend_context)
    if frontend_context_text:
        cleaned_input = f"{frontend_context_text}\n\nRichiesta utente:\n{cleaned_input}"
    resolved_paths = [resolve_attachment_path(path) for path in attachment_paths or []]
    attachment_lines = [f"- {path.name} ({_guess_mime_type(path)})" for path in resolved_paths]
    attachment_blocks = [_build_attachment_block(path) for path in resolved_paths]

    for attachment in inline_attachments or []:
        filename = attachment["filename"]
        mime_type = attachment["mime_type"]
        base64_payload = attachment["base64_data"]
        attachment_lines.append(f"- {filename} ({mime_type})")
        attachment_blocks.append(
            _build_attachment_block_from_payload(
                filename=filename,
                mime_type=mime_type,
                base64_payload=base64_payload,
            )
        )

    if not attachment_blocks:
        return cleaned_input

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": "\n".join(
                [
                    cleaned_input,
                    "",
                    "Allegati disponibili in questa richiesta:",
                    *attachment_lines,
                ]
            ),
        }
    ]
    content.extend(attachment_blocks)
    return content


def _format_frontend_context(frontend_context: dict[str, Any] | None) -> str | None:
    if not frontend_context:
        return None

    weekly_overview = frontend_context.get("weekly_overview")
    if not isinstance(weekly_overview, dict):
        return None

    weeks = weekly_overview.get("weeks")
    if not isinstance(weeks, list) or not weeks:
        return None

    lines = [
        "Contesto frontend corrente del riquadro settimanale in basso:",
        f"- mese visibile: {weekly_overview.get('month_label') or weekly_overview.get('month_start')}",
    ]

    default_week_index = weekly_overview.get("default_week_index")
    if isinstance(default_week_index, int):
        lines.append(f"- settimana frontend di default per richieste vaghe: Settimana {default_week_index}")

    lines.append("- settimane visibili:")
    for week in weeks:
        if not isinstance(week, dict):
            continue
        label = week.get("label") or f"Settimana {week.get('index')}"
        suffix = " [contiene oggi]" if week.get("contains_today") else ""
        lines.append(
            f"  - {label}: {week.get('start')} -> {week.get('end')}, spesa mostrata {week.get('total')} euro{suffix}"
        )

    lines.append(
        "- se l'utente parla della settimana mostrata sotto o di Settimana 1-5, usa queste finestre del frontend invece delle settimane ISO"
    )
    return "\n".join(lines)

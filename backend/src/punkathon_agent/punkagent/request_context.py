from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import date
from typing import Any

_frontend_context_var: ContextVar[dict[str, Any] | None] = ContextVar("frontend_context", default=None)
_current_user_id_var: ContextVar[int | None] = ContextVar("current_user_id", default=None)
_db_reload_required_var: ContextVar[bool] = ContextVar("db_reload_required", default=False)


def set_frontend_context(frontend_context: dict[str, Any] | None) -> Token[dict[str, Any] | None]:
    return _frontend_context_var.set(frontend_context)


def reset_frontend_context(token: Token[dict[str, Any] | None]) -> None:
    _frontend_context_var.reset(token)


def get_frontend_context() -> dict[str, Any] | None:
    return _frontend_context_var.get()


def set_current_user_id(user_id: int | None) -> Token[int | None]:
    return _current_user_id_var.set(user_id)


def reset_current_user_id(token: Token[int | None]) -> None:
    _current_user_id_var.reset(token)


def get_current_user_id() -> int | None:
    return _current_user_id_var.get()


def set_db_reload_required(value: bool = False) -> Token[bool]:
    return _db_reload_required_var.set(value)


def reset_db_reload_required(token: Token[bool]) -> None:
    _db_reload_required_var.reset(token)


def get_db_reload_required() -> bool:
    return _db_reload_required_var.get()


def mark_db_updated() -> None:
    _db_reload_required_var.set(True)


def get_default_frontend_week_window(*, today: date | None = None) -> dict[str, Any] | None:
    frontend_context = get_frontend_context()
    if not frontend_context:
        return None

    weekly_overview = frontend_context.get("weekly_overview")
    if not isinstance(weekly_overview, dict):
        return None

    weeks = weekly_overview.get("weeks")
    default_week_index = weekly_overview.get("default_week_index")
    if not isinstance(weeks, list) or not isinstance(default_week_index, int):
        return None

    target_week = next(
        (
            week
            for week in weeks
            if isinstance(week, dict) and int(week.get("index", 0)) == default_week_index
        ),
        None,
    )
    if target_week is None:
        return None

    start_raw = target_week.get("start")
    end_raw = target_week.get("end")
    if not isinstance(start_raw, str) or not isinstance(end_raw, str):
        return None

    start_date = date.fromisoformat(start_raw)
    end_date = date.fromisoformat(end_raw)
    reference_day = today or date.today()
    return {
        "label": str(target_week.get("label") or f"Settimana {default_week_index}"),
        "start_date": start_date,
        "end_date": end_date,
        "is_current": start_date <= reference_day <= end_date,
    }


__all__ = [
    "get_db_reload_required",
    "get_current_user_id",
    "get_default_frontend_week_window",
    "get_frontend_context",
    "mark_db_updated",
    "reset_current_user_id",
    "reset_db_reload_required",
    "reset_frontend_context",
    "set_current_user_id",
    "set_db_reload_required",
    "set_frontend_context",
]

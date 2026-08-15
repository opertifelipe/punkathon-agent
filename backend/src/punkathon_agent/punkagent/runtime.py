from __future__ import annotations

import inspect
import os
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Any

from deepagents import SubAgent, create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from dotenv import dotenv_values, load_dotenv
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, messages_from_dict
from langchain_openai import ChatOpenAI
from openai import AuthenticationError
from pydantic import BaseModel as PydanticBaseModel

from punkathon_agent.db import create_database

from .attachments import build_user_message_content
from .constants import AGENT_NAME, DEEPAGENTS_AGENT_NAME, DEEPAGENTS_BACKEND_ROOT, DEEPAGENTS_SKILL_SOURCES, ENV_PATH
from .prompts import (
    CATEGORY_ANALYST_SUBAGENT_PROMPT,
    GOAL_INSIGHTS_ANALYST_SUBAGENT_PROMPT,
    PERIOD_ANALYST_SUBAGENT_PROMPT,
    SYSTEM_PROMPT,
)
from .request_context import (
    get_db_reload_required,
    reset_current_user_id,
    reset_db_reload_required,
    reset_frontend_context,
    set_current_user_id,
    set_db_reload_required,
    set_frontend_context,
)
from .services import _inject_profile_context
from .tools import ANALYSIS_TOOLS, ROOT_TOOLS


def _resolve_openai_api_key() -> str | None:
    file_values = dotenv_values(ENV_PATH)
    file_key = file_values.get("OPENAI_API_KEY")
    env_key = os.getenv("OPENAI_API_KEY")
    return file_key or env_key


def _use_responses_api() -> bool:
    file_values = dotenv_values(ENV_PATH)
    raw_value = os.getenv("OPENAI_USE_RESPONSES_API")
    if raw_value is None:
        raw_value = file_values.get("OPENAI_USE_RESPONSES_API")
    if raw_value is None:
        return False
    return str(raw_value).strip().casefold() in {"1", "true", "yes", "on"}


def build_chat_model() -> ChatOpenAI:
    api_key = _resolve_openai_api_key()
    use_responses_api = _use_responses_api()
    kwargs: dict[str, Any] = {
        "model": "gpt-5.4-mini",
        "api_key": api_key,
        "use_responses_api": use_responses_api,
        "verbosity": "low",
    }
    if use_responses_api:
        kwargs["output_version"] = "responses/v1"
        kwargs["reasoning"] = {"summary": "auto", "effort": "medium"}
    return ChatOpenAI(**kwargs)


def _build_deepagents_backend() -> FilesystemBackend:
    return FilesystemBackend(root_dir=DEEPAGENTS_BACKEND_ROOT)


def _build_category_analyst_subagent() -> SubAgent:
    return {
        "name": "category-analyst",
        "description": (
            "Use this agent for category-level spend analysis, recurring charge reviews, fixed-cost readouts, "
            "and category-specific cost-cutting suggestions grounded in the stored data."
        ),
        "system_prompt": CATEGORY_ANALYST_SUBAGENT_PROMPT,
        "model": build_chat_model(),
        "tools": ANALYSIS_TOOLS,
    }


def _build_period_analyst_subagent() -> SubAgent:
    return {
        "name": "period-analyst",
        "description": (
            "Use this agent for week-specific, month-specific, or full-history spending analysis, "
            "especially when the user wants comparisons across periods or a historical audit."
        ),
        "system_prompt": PERIOD_ANALYST_SUBAGENT_PROMPT,
        "model": build_chat_model(),
        "tools": ANALYSIS_TOOLS,
    }


def _build_goal_insights_subagent() -> SubAgent:
    return {
        "name": "goal-insights-analyst",
        "description": (
            "Use this agent for weekly or monthly insights tied to the user's financial goal, "
            "including trajectory assessment, focus categories, and concrete next moves."
        ),
        "system_prompt": GOAL_INSIGHTS_ANALYST_SUBAGENT_PROMPT,
        "model": build_chat_model(),
        "tools": ANALYSIS_TOOLS,
    }


def create_punk_agent() -> Any:
    load_dotenv(ENV_PATH, override=True)
    create_database()
    return create_deep_agent(
        model=build_chat_model(),
        tools=ROOT_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        subagents=[
            _build_category_analyst_subagent(),
            _build_period_analyst_subagent(),
            _build_goal_insights_subagent(),
        ],
        skills=DEEPAGENTS_SKILL_SOURCES,
        backend=_build_deepagents_backend(),
        name=DEEPAGENTS_AGENT_NAME,
    )


def create_banking_agent() -> Any:
    return create_punk_agent()


@lru_cache(maxsize=1)
def get_punk_agent() -> Any:
    return create_punk_agent()


def get_banking_agent() -> Any:
    return get_punk_agent()


def extract_final_answer(messages: list[Any]) -> str:
    for message in reversed(messages):
        if not isinstance(message, AIMessage):
            continue

        content_blocks = getattr(message, "content_blocks", None)
        if isinstance(content_blocks, list):
            parts: list[str] = []
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text"):
                    parts.append(str(block["text"]))
            if parts:
                return "".join(parts).strip()

        if isinstance(message.content, str) and message.content.strip():
            return message.content.strip()

        if isinstance(message.content, list):
            parts = []
            for item in message.content:
                if isinstance(item, str) and item:
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]))
            if parts:
                return "".join(parts).strip()

    return f"{AGENT_NAME} non e' riuscito a produrre una risposta finale."


def _normalize_conversation(
    conversation: list[BaseMessage | dict[str, Any]],
) -> list[BaseMessage | dict[str, Any]]:
    normalized: list[BaseMessage | dict[str, Any]] = []

    for message in conversation:
        if isinstance(message, BaseMessage):
            normalized.append(message)
            continue

        if isinstance(message, dict) and "type" in message and "data" in message:
            normalized.append(messages_from_dict([message])[0])
            continue

        normalized.append(message)

    return normalized


def _sanitize_serializable_message_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value

    if isinstance(value, BaseMessage):
        return _safe_message_to_dict(value)

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "parsed":
                continue
            sanitized[str(key)] = _sanitize_serializable_message_value(item)
        return sanitized

    if isinstance(value, (list, tuple, set)):
        return [_sanitize_serializable_message_value(item) for item in value]

    if isinstance(value, PydanticBaseModel):
        return _sanitize_serializable_message_value(getattr(value, "__dict__", {}))

    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except TypeError:
            pass

    if hasattr(value, "__dict__"):
        raw_dict = getattr(value, "__dict__", None)
        if isinstance(raw_dict, dict):
            return _sanitize_serializable_message_value(raw_dict)

    return str(value)


def _safe_message_to_dict(message: BaseMessage) -> dict[str, Any]:
    raw_data = getattr(message, "__dict__", {})
    sanitized_data = _sanitize_serializable_message_value(raw_data)
    if not isinstance(sanitized_data, dict):
        raise TypeError(f"Payload messaggio non serializzabile: {type(sanitized_data)!r}")
    return {"type": message.type, "data": sanitized_data}


def serialize_conversation(messages: list[BaseMessage | dict[str, Any]]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []

    for message in messages:
        if isinstance(message, BaseMessage):
            serialized.append(_safe_message_to_dict(message))
        elif isinstance(message, dict):
            sanitized = _sanitize_serializable_message_value(message)
            if not isinstance(sanitized, dict):
                raise TypeError(f"Formato messaggio non serializzabile: {type(sanitized)!r}")
            serialized.append(sanitized)
        else:
            raise TypeError(f"Formato messaggio non serializzabile: {type(message)!r}")

    return serialized


def _build_agent_turn_input(
    conversation: list[BaseMessage | dict[str, Any]],
    user_input: str,
    attachment_paths: list[str | os.PathLike[str]] | None = None,
    inline_attachments: list[dict[str, str]] | None = None,
    frontend_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_conversation = _normalize_conversation(conversation)
    user_content = _inject_profile_context(
        build_user_message_content(
            user_input,
            attachment_paths=attachment_paths,
            inline_attachments=inline_attachments,
            frontend_context=frontend_context,
        )
    )
    return {
        "messages": [
            *normalized_conversation,
            {"role": "user", "content": user_content},
        ]
    }


def _iter_message_blocks(message: AIMessage | AIMessageChunk) -> Iterator[tuple[str, str, str | None]]:
    saw_structured_block = False
    content_blocks = getattr(message, "content_blocks", None)

    if isinstance(content_blocks, list):
        for block in content_blocks:
            if not isinstance(block, dict):
                continue

            saw_structured_block = True
            block_type = block.get("type")
            phase = block.get("phase") if isinstance(block.get("phase"), str) else None

            if block_type == "reasoning":
                reasoning = block.get("reasoning")
                if reasoning:
                    yield "reasoning", str(reasoning), phase
            elif block_type == "text":
                text = block.get("text")
                if text:
                    yield "text", str(text), phase

    if saw_structured_block:
        return

    content = message.content
    if isinstance(content, str):
        if content:
            yield "text", content, None
        return

    if not isinstance(content, list):
        return

    for block in content:
        if isinstance(block, str):
            if block:
                yield "text", block, None
            continue

        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        phase = block.get("phase") if isinstance(block.get("phase"), str) else None
        if block_type == "reasoning":
            reasoning = block.get("reasoning")
            if reasoning:
                yield "reasoning", str(reasoning), phase
        elif block_type == "text":
            text = block.get("text")
            if text:
                yield "text", str(text), phase


def _stream_events_from_chunk(chunk: dict[str, Any]) -> list[dict[str, str]]:
    if chunk.get("type") != "messages":
        return []

    data = chunk.get("data")
    if not isinstance(data, tuple) or len(data) != 2:
        return []

    message, _metadata = data
    if not isinstance(message, (AIMessage, AIMessageChunk)):
        return []

    namespaces = chunk.get("ns") or ()
    is_subagent = any(isinstance(namespace, str) and namespace.startswith("tools:") for namespace in namespaces)
    events: list[dict[str, str]] = []

    for block_type, chunk_text, phase in _iter_message_blocks(message):
        event_type = "reasoning" if block_type == "reasoning" or phase == "commentary" or is_subagent else "answer"
        if chunk_text:
            events.append({"type": event_type, "content": chunk_text})

    return events


async def run_agent_turn_streaming(
    agent: Any,
    conversation: list[BaseMessage | dict[str, Any]],
    user_input: str,
    attachment_paths: list[str | os.PathLike[str]] | None = None,
    inline_attachments: list[dict[str, str]] | None = None,
    frontend_context: dict[str, Any] | None = None,
    user_id: int | None = None,
    on_event: Callable[[dict[str, str]], Any] | None = None,
) -> tuple[str, list[BaseMessage | dict[str, Any]], bool]:
    token = set_frontend_context(frontend_context)
    user_token = set_current_user_id(user_id)
    reload_token = set_db_reload_required(False)
    try:
        agent_input = _build_agent_turn_input(
            conversation,
            user_input,
            attachment_paths=attachment_paths,
            inline_attachments=inline_attachments,
            frontend_context=frontend_context,
        )
        latest_messages = _normalize_conversation(conversation)

        try:
            async for chunk in agent.astream(
                agent_input,
                stream_mode=["messages", "values"],
                subgraphs=True,
                version="v2",
            ):
                if chunk.get("type") == "messages":
                    for event in _stream_events_from_chunk(chunk):
                        if on_event is None:
                            continue
                        maybe_awaitable = on_event(event)
                        if inspect.isawaitable(maybe_awaitable):
                            await maybe_awaitable
                    continue

                if chunk.get("type") != "values":
                    continue

                data = chunk.get("data")
                if isinstance(data, dict) and isinstance(data.get("messages"), list):
                    latest_messages = data["messages"]
        except AuthenticationError as exc:
            raise RuntimeError(
                "Autenticazione OpenAI fallita: verifica che OPENAI_API_KEY sia presente e valida nell'ambiente corrente."
            ) from exc

        return extract_final_answer(latest_messages), latest_messages, get_db_reload_required()
    finally:
        reset_db_reload_required(reload_token)
        reset_current_user_id(user_token)
        reset_frontend_context(token)


def run_agent_turn(
    agent: Any,
    conversation: list[BaseMessage | dict[str, Any]],
    user_input: str,
    attachment_paths: list[str | os.PathLike[str]] | None = None,
    inline_attachments: list[dict[str, str]] | None = None,
    frontend_context: dict[str, Any] | None = None,
    user_id: int | None = None,
) -> tuple[str, list[BaseMessage | dict[str, Any]], bool]:
    token = set_frontend_context(frontend_context)
    user_token = set_current_user_id(user_id)
    reload_token = set_db_reload_required(False)
    try:
        try:
            result = agent.invoke(
                _build_agent_turn_input(
                    conversation,
                    user_input,
                    attachment_paths=attachment_paths,
                    inline_attachments=inline_attachments,
                    frontend_context=frontend_context,
                )
            )
        except AuthenticationError as exc:
            raise RuntimeError(
                "Autenticazione OpenAI fallita: verifica che OPENAI_API_KEY sia presente e valida nell'ambiente corrente."
            ) from exc

        messages = result.get("messages", [])
        return extract_final_answer(messages), messages, get_db_reload_required()
    finally:
        reset_db_reload_required(reload_token)
        reset_current_user_id(user_token)
        reset_frontend_context(token)

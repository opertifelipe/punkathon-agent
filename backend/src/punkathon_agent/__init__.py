from __future__ import annotations

__all__ = [
    "AGENT_NAME",
    "create_punk_agent",
    "get_punk_agent",
    "run_agent_turn",
    "run_agent_turn_streaming",
]


def __getattr__(name: str):
    if name in __all__:
        from importlib import import_module

        punkagent = import_module("punkathon_agent.punkagent")
        return getattr(punkagent, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

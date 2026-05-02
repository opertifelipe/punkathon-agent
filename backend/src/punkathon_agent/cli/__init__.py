from __future__ import annotations

from .app import app, main


def __getattr__(name: str):
    if name == "api_app":
        from .api import app as fastapi_app

        return fastapi_app
    if name == "api_main":
        from .api import main as api_entrypoint

        return api_entrypoint
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["api_app", "api_main", "app", "main"]

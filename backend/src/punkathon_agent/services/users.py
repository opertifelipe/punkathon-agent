from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from punkathon_agent.auth import hash_password
from punkathon_agent.models.db import DEFAULT_USER_GOAL, MovimentoBancario, PunkUser, Utente

DEFAULT_CLI_USER_EMAIL = "cli@punkagent.local"
DEFAULT_CLI_USER_NAME = "Utente"
DEFAULT_CLI_USER_SURNAME = "CLI"
DEFAULT_CLI_USER_AGE = 30
DEFAULT_CLI_USER_PASSWORD = "cli-default-context"


def _profile_for_user(session: Session, user_id: int) -> Utente | None:
    return session.exec(select(Utente).where(Utente.user_id == user_id)).first()


def ensure_user_profile(session: Session, user_id: int) -> Utente:
    utente = _profile_for_user(session, user_id)
    changed = False

    if utente is None:
        utente = Utente(user_id=user_id)
        changed = True

    if not (utente.obiettivo or "").strip():
        utente.obiettivo = DEFAULT_USER_GOAL
        changed = True

    if changed:
        session.add(utente)
        session.commit()
        session.refresh(utente)

    return utente


def claim_legacy_data_for_first_user(session: Session, user_id: int) -> None:
    total_users = session.exec(select(func.count()).select_from(PunkUser)).one()
    if int(total_users or 0) != 1:
        ensure_user_profile(session, user_id)
        return

    legacy_profile = session.exec(
        select(Utente).where(Utente.user_id.is_(None)).order_by(Utente.id.asc())
    ).first()
    if legacy_profile is not None:
        legacy_profile.user_id = user_id
        if not (legacy_profile.obiettivo or "").strip():
            legacy_profile.obiettivo = DEFAULT_USER_GOAL
        session.add(legacy_profile)
    else:
        session.add(Utente(user_id=user_id, obiettivo=DEFAULT_USER_GOAL))

    orphan_movements = session.exec(
        select(MovimentoBancario).where(MovimentoBancario.user_id.is_(None))
    ).all()
    for movement in orphan_movements:
        movement.user_id = user_id
        session.add(movement)

    session.commit()


def resolve_default_cli_user(session: Session) -> PunkUser:
    user = session.exec(select(PunkUser).order_by(PunkUser.id.asc())).first()
    if user is None:
        user = PunkUser(
            email=DEFAULT_CLI_USER_EMAIL,
            nome=DEFAULT_CLI_USER_NAME,
            cognome=DEFAULT_CLI_USER_SURNAME,
            eta=DEFAULT_CLI_USER_AGE,
            password_hash=hash_password(DEFAULT_CLI_USER_PASSWORD),
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    if user.id is None:
        raise RuntimeError("Utente CLI senza identificatore persistito.")

    claim_legacy_data_for_first_user(session, user.id)
    return user


__all__ = [
    "DEFAULT_CLI_USER_AGE",
    "DEFAULT_CLI_USER_EMAIL",
    "DEFAULT_CLI_USER_NAME",
    "DEFAULT_CLI_USER_PASSWORD",
    "DEFAULT_CLI_USER_SURNAME",
    "claim_legacy_data_for_first_user",
    "ensure_user_profile",
    "resolve_default_cli_user",
]
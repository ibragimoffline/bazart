import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession


class AuthSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, user_id: int, jti: str, expires_at: datetime) -> AuthSession:
        session = AuthSession(user_id=user_id, current_jti=jti, expires_at=expires_at)
        self.db.add(session)
        self.db.flush()
        return session

    def get_for_update(self, session_id: uuid.UUID) -> AuthSession | None:
        """Qatorni qulflaydi: parallel refresh'lar rotation'ni ketma-ket ko'radi."""
        statement = select(AuthSession).where(AuthSession.id == session_id).with_for_update()
        return self.db.scalar(statement)

    def get(self, session_id: uuid.UUID) -> AuthSession | None:
        return self.db.get(AuthSession, session_id)

    def revoke(self, session: AuthSession, reason: str) -> None:
        if session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            session.revoke_reason = reason

    def revoke_all_for_user(self, user_id: int, reason: str) -> None:
        self.db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), revoke_reason=reason)
        )

import hashlib
import math
from datetime import timedelta

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert

from app.extensions import db
from app.models.security import LoginAttempt


class LoginRateLimiter:
    @classmethod
    def hit(cls, key, max_attempts, window_seconds):
        if max_attempts < 1 or window_seconds < 1:
            raise RuntimeError("Politica de tentativas invalida.")
        digest = hashlib.sha256(key.encode()).hexdigest()
        table = LoginAttempt.__table__
        with db.engine.begin() as connection:
            now = connection.execute(db.select(func.clock_timestamp())).scalar_one()
            connection.execute(delete(table).where(table.c.expires_at < now))
            statement = insert(table).values(
                key=digest, attempts=1, expires_at=now + timedelta(seconds=window_seconds),
            ).on_conflict_do_update(
                index_elements=[table.c.key],
                set_={"attempts": table.c.attempts + 1},
            ).returning(table.c.attempts, table.c.expires_at)
            attempts, expires = connection.execute(statement).one()
        return (True, 0) if attempts <= max_attempts else (False, max(1, math.ceil((expires - now).total_seconds())))

    @classmethod
    def clear(cls, key):
        with db.engine.begin() as connection:
            connection.execute(delete(LoginAttempt).where(LoginAttempt.key == hashlib.sha256(key.encode()).hexdigest()))

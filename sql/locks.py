import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.scoping import scoped_session
from flask_sqlalchemy import SQLAlchemy
from contextlib import contextmanager

from typing import Tuple, Generator


class AdvisoryLock:
    """
    # Abstracts acquiring Postgres session level locks  #

    The idea is that if process P acquires lock L (with a key K) from session S,
    another process P2 from another session S2 won't be able to acquire another lock L2 with the same key (K).
    """

    def __init__(self, engine: SQLAlchemy, lock_key: str):
        self.session = sessionmaker(bind=engine)
        self.lock_key = lock_key

    @contextmanager
    def grab_lock(self) -> Generator[Tuple[bool, scoped_session], None, None]:
        """
        Yields a boolean value and a new SQLAlchemy session object.
        The process calling this method should only execute transactions via the session object if the boolean returned is True


        -- Grab lock *
        SELECT pg_try_advisory_lock(23);

        -- Release lock **
        SELECT pg_advisory_unlock(23);

        -- List all advisory locks (all sessions)
        SELECT mode, classid, objid FROM pg_locks WHERE locktype = 'advisory';

        #############################
        #       EXAMPLE USAGE       #
        #############################

        with AdvisoryLock(engine=db.engine, lock_key="6bd4cf27-d68a-4d8a-809c-b07815937052").grab_lock() as locked_session:
            lock, session = locked_session
            if lock:
                # Do stuff with session
                user = session.query(User).filter_by(id=100).first()
                user.hint = "someotherhint"
                session.add(user)
        """
        session = self.session()
        try:
            advisory_lock_key = int(
                hashlib.sha1(self.lock_key.encode("utf-8")).hexdigest(), 16
            ) % (10 ** 8)

            # *
            advisory_lock = session.execute(
                select([func.pg_try_advisory_lock(advisory_lock_key)])
            ).fetchone()[0]

            yield (advisory_lock, session)

            # **
            session.execute(select([func.pg_advisory_unlock(advisory_lock_key)]))

        except:
            session.rollback()
            raise

        finally:
            session.commit()
            session.close()

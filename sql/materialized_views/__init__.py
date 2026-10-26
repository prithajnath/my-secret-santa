import logging
from sqlalchemy.exc import ProgrammingError, NoSuchTableError
from sqlalchemy import text
from sqlalchemy.schema import Table, MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from functools import cached_property

logger = logging.getLogger(__name__)


class MaterializedView:
    def __init__(self, name, conn, ddl):
        self.name = name
        self.conn = conn
        self.ddl = ddl

    def create(self):
        try:
            with self.conn.engine.begin() as connection:
                logger.info(f"creating mat view {self.name}")
                connection.execute(text(self.ddl))
        except ProgrammingError as e:
            if f"relation '{self.name}'already exists" in e.__str__():
                logger.debug(
                    f"Materialized view {self.name} already exists. Skipping creation"
                )

    def refresh(self):
        logger.debug(f"refreshing materialized view {self.name}")
        with self.conn.engine.begin() as connection:
            connection.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {self.name}"))

    def drop(self):
        with self.conn.engine.begin() as connection:
            connection.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {self.name}"))

    @property
    def query(self):
        return self.conn.session.query(self._view)

    @cached_property
    def _view(self):
        try:
            _table = type(
                self.name,
                (declarative_base(),),
                {
                    "__table__": Table(
                        self.name,
                        MetaData(),
                        self.conn.Column("id", UUID(as_uuid=True), primary_key=True),
                        autoload_with=self.conn.engine,
                    )
                },
            )

        except NoSuchTableError:
            self.create()
            _table = type(
                self.name,
                (declarative_base(),),
                {
                    "__table__": Table(
                        self.name,
                        MetaData(),
                        self.conn.Column("id", UUID(as_uuid=True), primary_key=True),
                        autoload_with=self.conn.engine,
                    )
                },
            )
        return _table


class AllLatestPairsView(MaterializedView):
    def __init__(self, conn):
        from .all_latest_pairs_view import ddl

        super().__init__("all_latest_pairs_view", conn, ddl)

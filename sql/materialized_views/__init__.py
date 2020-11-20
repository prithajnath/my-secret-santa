from sqlalchemy.exc import ProgrammingError
from sqlalchemy.schema import Table, MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from functools import cached_property


class MaterializedView:
    def __init__(self, name, conn, ddl):
        self.name = name
        self.conn = conn
        self.ddl = ddl

    def create(self):
        try:
            self.conn.engine.execute(self.ddl)
        except ProgrammingError as e:
            if f"relation '{self.name}'already exists" in e.__str__():
                print(
                    f"Materialized view {self.name} already exists. Skipping creation"
                )

    def refresh(self):
        print(f"refreshing materialized view {self.name}")
        with self.conn.engine.begin() as connection:
            connection.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {self.name}")

    def drop(self):
        self.conn.engine.execute(f"DROP MATERIALIZED VIEW IF EXISTS {self.name}")

    @property
    def query(self):
        return self.conn.session.query(self._view)

    @cached_property
    def _view(self):
        return type(
            self.name,
            (declarative_base(),),
            {
                "__table__": Table(
                    self.name,
                    MetaData(bind=self.conn.engine),
                    self.conn.Column("id", UUID(as_uuid=True), primary_key=True),
                    autoload_with=self.conn.engine,
                )
            },
        )


class AllAdminView(MaterializedView):
    def __init__(self, conn):
        from .all_admin_view import ddl

        super().__init__("all_admin_view", conn, ddl)

from sqlalchemy.exc import ProgrammingError

class MaterializedView:
    def __init__(self, name, conn, ddl):
        self.name = name
        self.conn = conn
        self.ddl = ddl

    def create(self):
        try:
            self.conn.engine.execute(self.ddl)
        except ProgrammingError as e:
            if 'relation "all_admin_view" already exists' in e.__str__():
                print(f"Materialized view {self.name} already exists. Skipping creation")

    def refresh(self):
        self.conn.engine.execute(f"REFRESH MATERIALIZED VIEW {self.name}")

    def drop(self):
        self.conn.engine.execute(f"DROP MATERIALIZED VIEW IF EXISTS {self.name}")


class AllAdminView(MaterializedView):
    def __init__(self, conn):
        from .all_admin_view import ddl

        super().__init__("all_admin_view", conn, ddl)

class MaterializedView:
    def __init__(self, name, conn, ddl):
        self.name = name
        self.conn = conn
        self.ddl = ddl

    def create(self):
        result = self.conn.engine.execute(
            f"SELECT * FROM pg_tables WHERE tablename='{self.name}';"
        )

        if not result.fetchall():
            self.conn.engine.execute(self.ddl)

    def refresh(self):
        self.conn.engine.execute(f"REFRESH MATERIALIZED VIEW {self.name}")

    def drop(self):
        self.conn.engine.execute(f"DROP MATERIALIZED VIEW IF EXISTS {self.name}")


class AllAdminView(MaterializedView):
    def __init__(self, conn):
        from .all_admin_view import ddl

        super().__init__("all_admin_view", conn, ddl)

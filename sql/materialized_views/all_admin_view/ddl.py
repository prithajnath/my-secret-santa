import os

app_root = os.getenv("APP_ROOT")

with open(
    os.path.join(app_root, "sql", "materialized_views", "all_admin_view", "ddl.sql"),
    "r",
) as f:
    ddl = "".join(f.readlines())

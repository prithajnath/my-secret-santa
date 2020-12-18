import os

app_root = os.getenv("APP_ROOT")

with open(
    os.path.join(
        app_root, "sql", "materialized_views", "all_latest_pairs_view", "ddl.sql"
    ),
    "r",
) as f:
    ddl = "".join(f.readlines())

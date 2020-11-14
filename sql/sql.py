import os

sql_dir = os.path.join(os.getenv("APP_ROOT"), "sql")
queries = {}
for sql_file in os.listdir(sql_dir):
    with open(os.path.join(sql_dir, sql_file)) as f:
        queries[sql_file] = "".join(f.readlines())

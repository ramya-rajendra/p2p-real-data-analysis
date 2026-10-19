"""Runs every query in sql/queries.sql with DuckDB and prints the results.

Run from the project root:  python src/run_sql.py
"""
from pathlib import Path

import duckdb

sql = Path("sql/queries.sql").read_text(encoding="utf-8")
con = duckdb.connect()

for block in sql.split(";"):
    lines = [l for l in block.strip().splitlines() if l.strip()]
    query = "\n".join(l for l in lines if not l.strip().startswith("--"))
    if not query:
        continue
    comments = [l.strip("- ").strip() for l in lines if l.strip().startswith("--")]
    title = next((c for c in comments if c[:1].isdigit()), "")
    print(f"\n=== {title} ===")
    print(con.sql(query))

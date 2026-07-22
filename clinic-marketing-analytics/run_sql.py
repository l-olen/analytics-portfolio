import sqlite3, sys
from pathlib import Path

sql_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
db = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/medical.db")

if not sql_file:
    print("Использование: python run_sql.py sql/01_funnel_medical.sql [data/medical.db]")
    sys.exit(1)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cursor = conn.execute(sql_file.read_text(encoding="utf-8"))

rows = cursor.fetchall()
if not rows:
    print("(пусто)")
    sys.exit(0)

cols = rows[0].keys()
widths = [max(len(c), max(len(str(r[c])) for r in rows)) for c in cols]

header = "  ".join(c.ljust(w) for c, w in zip(cols, widths))
print(header)
print("-" * len(header))
for row in rows:
    print("  ".join(str(row[c]).ljust(w) for c, w in zip(cols, widths)))
print(f"\n{len(rows)} строк")

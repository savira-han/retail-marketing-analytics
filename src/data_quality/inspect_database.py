
from pathlib import Path
import duckdb


# --------------------------------------------------
# 1. DATABASE CONNECTION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "retail_marketing.duckdb"

print("\n========== DATABASE CONNECTION ==========")
print(f"Project root: {PROJECT_ROOT}")
print(f"Database path: {DB_PATH.resolve()}")
print(f"File exists: {DB_PATH.exists()}")

con = duckdb.connect(str(DB_PATH), read_only=True)


# --------------------------------------------------
# 2. IDENTIFY DATABASES
# --------------------------------------------------

print("\n========== ATTACHED DATABASES ==========")

databases = con.execute("PRAGMA database_list").fetchdf()
print(databases.to_string(index=False))


# --------------------------------------------------
# 3. IDENTIFY ALL TABLES AND SCHEMAS
# --------------------------------------------------

print("\n========== ALL DATABASE TABLES ==========")

tables = con.execute("""
    SELECT
        table_catalog,
        table_schema,
        table_name,
        table_type
    FROM information_schema.tables
    WHERE table_schema = 'raw'
    and table_type = 'BASE TABLE'
    ORDER BY table_name
""").fetchdf()

if tables.empty:
    print("No tables found in this database connection.")
else:
    print(tables.to_string(index=False))


# --------------------------------------------------
# 4. ROW COUNTS
# --------------------------------------------------

print("\n========== TABLE ROW COUNTS ==========")

for _, table in tables.iterrows():

    if table["table_type"] != "BASE TABLE":
        continue

    schema = table["table_schema"]
    name = table["table_name"]

    row_count = con.execute(
        f'SELECT COUNT(*) FROM "{schema}"."{name}"'
    ).fetchone()[0]

    print(f"{schema}.{name}: {row_count:,} rows")


# --------------------------------------------------
# 5. CLOSE CONNECTION
# --------------------------------------------------

con.close()

print("\nDatabase inspection completed.")

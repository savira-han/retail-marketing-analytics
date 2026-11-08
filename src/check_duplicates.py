
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "raw" / "causal_data.csv"

connection = duckdb.connect()

connection.execute("SET memory_limit = '2GB'")
connection.execute("SET threads = 2")

print("Checking causal_data.csv for exact duplicate rows...")
print("This may take some time because the file contains approximately 36.8 million rows.")

result = connection.execute(
    """
    SELECT
        COUNT(*) AS total_rows,
        COUNT(DISTINCT (
            PRODUCT_ID,
            STORE_ID,
            WEEK_NO,
            display,
            mailer
        )) AS distinct_rows
    FROM read_csv_auto(?, sample_size = 20480)
    """,
    [str(CSV_PATH)],
).fetchone()

total_rows, distinct_rows = result
duplicate_rows = total_rows - distinct_rows

print("\n" + "=" * 60)
print("CAUSAL DATA DUPLICATE CHECK")
print("=" * 60)
print(f"Total rows:          {total_rows:,}")
print(f"Distinct rows:       {distinct_rows:,}")
print(f"Exact duplicate rows: {duplicate_rows:,}")

if duplicate_rows == 0:
    print("\nResult: No exact duplicate rows found.")
else:
    print(f"\nResult: {duplicate_rows:,} exact duplicate rows found.")

connection.close()

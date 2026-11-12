
from pathlib import Path
from datetime import datetime, timezone

import duckdb


# --------------------------------------------------
# 1. Database connection
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "retail_marketing.duckdb"

con = duckdb.connect(str(DATABASE_PATH))


# --------------------------------------------------
# 2. Discover raw tables and columns
# --------------------------------------------------

tables = con.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'raw'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name
""").fetchall()

assessed_at = datetime.now(timezone.utc).replace(tzinfo=None)

results = []


# --------------------------------------------------
# 3. Consistency assessment
# --------------------------------------------------

def quote_identifier(identifier):
    """Safely quote a SQL identifier."""
    return '"' + identifier.replace('"', '""') + '"'


for (table_name,) in tables:

    columns = con.execute(
        f"DESCRIBE raw.{quote_identifier(table_name)}"
    ).fetchall()

    for column in columns:

        column_name = column[0]
        data_type = column[1]

        # This assessment applies to string columns only.
        if data_type.upper() != "VARCHAR":
            continue

        table_identifier = quote_identifier(table_name)
        column_identifier = quote_identifier(column_name)

        query = f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (
                    WHERE {column_identifier} IS NOT NULL
                      AND TRIM({column_identifier}) <> ''
                      AND {column_identifier} <> TRIM({column_identifier})
                ) AS inconsistent_rows
            FROM raw.{table_identifier}
        """

        total_rows, inconsistent_rows = con.execute(query).fetchone()

        results.append({
            "table_name": table_name,
            "column_name": column_name,
            "check_type": "whitespace_consistency",
            "total_rows": total_rows,
            "inconsistent_rows": inconsistent_rows,
            "validation_rule": (
                "Non-NULL string values must not contain "
                "leading or trailing whitespace."
            ),
            "assessed_at": assessed_at,
        })


# --------------------------------------------------
# 4. Save assessment results
# --------------------------------------------------

con.execute("CREATE SCHEMA IF NOT EXISTS quality")

con.execute("""
    CREATE OR REPLACE TABLE quality.consistency_results (
        table_name VARCHAR,
        column_name VARCHAR,
        check_type VARCHAR,
        total_rows BIGINT,
        inconsistent_rows BIGINT,
        validation_rule VARCHAR,
        assessed_at TIMESTAMP
    )
""")

con.executemany(
    """
    INSERT INTO quality.consistency_results
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    [
        (
            row["table_name"],
            row["column_name"],
            row["check_type"],
            row["total_rows"],
            row["inconsistent_rows"],
            row["validation_rule"],
            row["assessed_at"],
        )
        for row in results
    ],
)


# --------------------------------------------------
# 5. Print assessment summary
# --------------------------------------------------

print("\nCONSISTENCY ASSESSMENT SUMMARY")
print("=" * 100)

summary = con.execute("""
    SELECT
        table_name,
        column_name,
        check_type,
        total_rows,
        inconsistent_rows,
        CASE
            WHEN inconsistent_rows = 0 THEN 'PASS'
            ELSE 'REVIEW'
        END AS status
    FROM quality.consistency_results
    ORDER BY table_name, column_name
""").fetchdf()

print(summary.to_string(index=False))

print("\nASSESSMENT TOTALS")
print("=" * 100)

total_checks = len(results)

passed_checks = sum(
    row["inconsistent_rows"] == 0
    for row in results
)

review_checks = total_checks - passed_checks

total_inconsistent_rows = sum(
    row["inconsistent_rows"]
    for row in results
)

print(f"Total validation checks       : {total_checks}")
print(f"Passed checks                 : {passed_checks}")
print(f"Checks requiring review       : {review_checks}")
print(f"Total column-level occurrences: {total_inconsistent_rows}")

print("\nResults saved to quality.consistency_results")

con.close()

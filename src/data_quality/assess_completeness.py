
from pathlib import Path
from datetime import datetime, timezone

import duckdb


# --------------------------------------------------
# 1. DATABASE CONNECTION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "retail_marketing.duckdb"

con = duckdb.connect(str(DB_PATH))


# --------------------------------------------------
# 2. HELPER: QUOTE SQL IDENTIFIERS
# --------------------------------------------------

def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


# --------------------------------------------------
# 3. IDENTIFY RAW TABLES
# --------------------------------------------------

tables = con.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'raw'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name
""").fetchall()

print("\n========== COMPLETENESS ASSESSMENT ==========")
print(f"Tables identified: {len(tables)}")


# --------------------------------------------------
# 4. PREPARE RESULTS
# --------------------------------------------------

results = []

assessment_time = datetime.now(timezone.utc)


# --------------------------------------------------
# 5. ASSESS EACH TABLE
# --------------------------------------------------

for (table_name,) in tables:

    qualified_table = (
        f'"raw".{quote_identifier(table_name)}'
    )

    # Retrieve column names and data types
    columns = con.execute(
        f"DESCRIBE {qualified_table}"
    ).fetchall()

    if not columns:
        continue

    # Build one aggregate query per table.
    # This avoids scanning large tables separately
    # for every individual column.

    expressions = []

    for index, column in enumerate(columns):

        column_name = column[0]
        data_type = column[1]

        quoted_column = quote_identifier(column_name)

        null_alias = f"null_{index}"
        expressions.append(
            f"COUNT(*) FILTER (WHERE {quoted_column} IS NULL) "
            f"AS {quote_identifier(null_alias)}"
        )

        # Empty or whitespace-only strings
        # are assessed separately from NULL values.
        if data_type.upper().startswith("VARCHAR"):
            blank_alias = f"blank_{index}"

            expressions.append(
                f"COUNT(*) FILTER ("
                f"WHERE {quoted_column} IS NOT NULL "
                f"AND TRIM({quoted_column}) = ''"
                f") AS {quote_identifier(blank_alias)}"
            )

    query = f"""
        SELECT
            COUNT(*) AS total_rows,
            {', '.join(expressions)}
        FROM {qualified_table}
    """

    assessment = con.execute(query).fetchone()

    total_rows = assessment[0]
    value_index = 1

    print(f"\nAssessing: {table_name}")

    for index, column in enumerate(columns):

        column_name = column[0]
        data_type = column[1]

        null_count = assessment[value_index]
        value_index += 1

        blank_count = 0

        if data_type.upper().startswith("VARCHAR"):
            blank_count = assessment[value_index]
            value_index += 1

        missing_count = null_count + blank_count

        missing_pct = (
            (missing_count / total_rows) * 100
            if total_rows > 0
            else 0
        )

        results.append((
            table_name,
            column_name,
            data_type,
            total_rows,
            null_count,
            blank_count,
            missing_count,
            missing_pct,
            assessment_time
        ))

        print(
            f"  {column_name}: "
            f"NULL={null_count:,}, "
            f"Blank={blank_count:,}, "
            f"Missing={missing_pct:.2f}%"
        )


# --------------------------------------------------
# 6. STORE RESULTS IN DUCKDB
# --------------------------------------------------

con.execute("CREATE SCHEMA IF NOT EXISTS quality")

con.execute("""
    CREATE OR REPLACE TABLE quality.completeness_results (
        table_name VARCHAR,
        column_name VARCHAR,
        data_type VARCHAR,
        total_rows BIGINT,
        null_count BIGINT,
        blank_count BIGINT,
        missing_count BIGINT,
        missing_pct DOUBLE,
        assessed_at TIMESTAMPTZ
    )
""")

if results:
    con.executemany("""
        INSERT INTO quality.completeness_results
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, results)


# --------------------------------------------------
# 7. DISPLAY SUMMARY
# --------------------------------------------------

summary = con.execute("""
    SELECT
        table_name,
        COUNT(*) AS columns_assessed,
        SUM(null_count) AS total_nulls,
        SUM(blank_count) AS total_blanks,
        SUM(missing_count) AS total_missing_columns
    FROM quality.completeness_results
    GROUP BY table_name
    ORDER BY table_name
""").fetchdf()

print("\n========== ASSESSMENT SUMMARY ==========")
print(summary.to_string(index=False))

print("\nResults stored in:")
print("quality.completeness_results")

con.close()

print("\nCompleteness assessment completed.")
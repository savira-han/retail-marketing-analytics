
from pathlib import Path

import duckdb
import pandas as pd


# --------------------------------------------------
# 1. Database connection
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "retail_marketing.duckdb"

con = duckdb.connect(str(DB_PATH))


# --------------------------------------------------
# 2. Candidate key definitions
# --------------------------------------------------

CANDIDATE_KEYS = {
    "campaign_desc": ["CAMPAIGN"],
    "hh_demographic": ["household_key"],
    "product": ["PRODUCT_ID"],
    "transaction_data": [
        "household_key",
        "BASKET_ID",
        "PRODUCT_ID",
        "TRANS_TIME",
    ],
    "causal_data": [
        "PRODUCT_ID",
        "STORE_ID",
        "WEEK_NO",
        "display",
        "mailer",
    ],
}


# --------------------------------------------------
# 3. Helper functions
# --------------------------------------------------

def quote_identifier(identifier):
    """Safely quote a DuckDB SQL identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def get_raw_tables():
    """Retrieve all base tables from the raw schema."""

    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'raw'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """

    return [
        row[0]
        for row in con.execute(query).fetchall()
    ]


def get_table_columns(table_name):
    """Retrieve column names from a raw table."""

    query = f"DESCRIBE raw.{quote_identifier(table_name)}"

    result = con.execute(query).fetchdf()

    return result["column_name"].tolist()


# --------------------------------------------------
# 4. Exact duplicate assessment
# --------------------------------------------------

def assess_exact_duplicates(table_name, columns):

    quoted_columns = ", ".join(
        quote_identifier(column)
        for column in columns
    )

    query = f"""
        SELECT
            COUNT(*) AS duplicate_groups,
            COALESCE(SUM(row_count - 1), 0) AS duplicate_rows
        FROM (
            SELECT COUNT(*) AS row_count
            FROM raw.{quote_identifier(table_name)}
            GROUP BY {quoted_columns}
            HAVING COUNT(*) > 1
        ) duplicates;
    """

    result = con.execute(query).fetchone()

    return {
        "table_name": table_name,
        "check_type": "exact_duplicates",
        "columns_checked": ", ".join(columns),
        "duplicate_groups": result[0],
        "duplicate_rows": result[1],
    }


# --------------------------------------------------
# 5. Candidate key uniqueness assessment
# --------------------------------------------------

def assess_candidate_key(table_name, key_columns):

    quoted_columns = ", ".join(
        quote_identifier(column)
        for column in key_columns
    )

    query = f"""
        SELECT
            COUNT(*) AS duplicate_groups,
            COALESCE(SUM(row_count - 1), 0) AS duplicate_rows
        FROM (
            SELECT COUNT(*) AS row_count
            FROM raw.{quote_identifier(table_name)}
            GROUP BY {quoted_columns}
            HAVING COUNT(*) > 1
        ) duplicates;
    """

    result = con.execute(query).fetchone()

    return {
        "table_name": table_name,
        "check_type": "candidate_key",
        "columns_checked": ", ".join(key_columns),
        "duplicate_groups": result[0],
        "duplicate_rows": result[1],
    }


# --------------------------------------------------
# 6. Run uniqueness assessment
# --------------------------------------------------

def run_uniqueness_assessment():

    tables = get_raw_tables()

    results = []

    print("\nStarting uniqueness assessment...\n")

    for table_name in tables:

        columns = get_table_columns(table_name)

        print(f"Assessing exact duplicates: {table_name}")

        exact_result = assess_exact_duplicates(
            table_name,
            columns
        )

        results.append(exact_result)

        if table_name in CANDIDATE_KEYS:

            print(f"Assessing candidate key: {table_name}")

            key_result = assess_candidate_key(
                table_name,
                CANDIDATE_KEYS[table_name]
            )

            results.append(key_result)

    return results


# --------------------------------------------------
# 7. Store assessment results
# --------------------------------------------------

def save_results(results):

    con.execute("CREATE SCHEMA IF NOT EXISTS quality")

    con.execute("""
        CREATE OR REPLACE TABLE quality.uniqueness_results (
            table_name VARCHAR,
            check_type VARCHAR,
            columns_checked VARCHAR,
            duplicate_groups BIGINT,
            duplicate_rows BIGINT,
            assessed_at TIMESTAMP
        );
    """)

    for result in results:

        con.execute("""
            INSERT INTO quality.uniqueness_results
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
        """, [
            result["table_name"],
            result["check_type"],
            result["columns_checked"],
            result["duplicate_groups"],
            result["duplicate_rows"],
        ])


# --------------------------------------------------
# 8. Display assessment summary
# --------------------------------------------------

def display_results():

    query = """
        SELECT
            table_name,
            check_type,
            columns_checked,
            duplicate_groups,
            duplicate_rows
        FROM quality.uniqueness_results
        ORDER BY table_name, check_type;
    """

    result = con.execute(query).fetchdf()

    print("\nUniqueness Assessment Results")
    print("=" * 100)
    print(result.to_string(index=False))


# --------------------------------------------------
# 9. Main execution
# --------------------------------------------------

def main():

    results = run_uniqueness_assessment()

    save_results(results)

    display_results()

    print("\nUniqueness assessment completed.")

    con.close()


if __name__ == "__main__":
    main()
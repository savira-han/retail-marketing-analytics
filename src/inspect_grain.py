
from pathlib import Path

import duckdb


# --------------------------------------------------
# Project configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_DIR = PROJECT_ROOT / "reports"
TEMP_DIR = REPORT_DIR / "duckdb_temp"

OUTPUT_PATH = REPORT_DIR / "grain_assessment.csv"


# Candidate keys to investigate.
# These are hypotheses, not confirmed primary keys.

CANDIDATE_KEYS = {
    "transaction_data": [
        ["household_key", "BASKET_ID", "PRODUCT_ID", "TRANS_TIME"],
    ],
    "hh_demographic": [
        ["household_key"],
    ],
    "product": [
        ["PRODUCT_ID"],
    ],
    "campaign_desc": [
        ["CAMPAIGN"],
    ],
    "campaign_table": [
        ["household_key", "CAMPAIGN"],
    ],
    "coupon": [
        ["COUPON_UPC", "PRODUCT_ID", "CAMPAIGN"],
    ],
    "coupon_redempt": [
        ["household_key", "DAY", "COUPON_UPC", "CAMPAIGN"],
    ],
    "causal_data": [
        ["PRODUCT_ID", "STORE_ID", "WEEK_NO","display","mailer"],
    ],
}


# --------------------------------------------------
# SQL helpers
# --------------------------------------------------

def quote_identifier(identifier: str) -> str:
    """Safely quote a SQL identifier."""

    return '"' + identifier.replace('"', '""') + '"'


def load_source_views(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """Register source CSV files as temporary views."""

    for dataset in CANDIDATE_KEYS:

        path = DATA_DIR / f"{dataset}.csv"

        if not path.exists():
            raise FileNotFoundError(
                f"Source file not found: {path}"
            )

        sql_path = str(path.resolve()).replace("'", "''")

        connection.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW
            {quote_identifier(dataset)} AS

            SELECT *
            FROM read_csv_auto(
                '{sql_path}',
                header = true
            )
            """
        )


# --------------------------------------------------
# Grain assessment
# --------------------------------------------------

def assess_candidate_key(
    connection: duckdb.DuckDBPyConnection,
    dataset: str,
    candidate_key: list[str],
) -> dict:
    """Evaluate uniqueness and null values for a candidate key."""

    table = quote_identifier(dataset)

    columns = ", ".join(
        quote_identifier(column)
        for column in candidate_key
    )

    null_condition = " OR ".join(
        f"{quote_identifier(column)} IS NULL"
        for column in candidate_key
    )

    row_count = connection.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    null_key_rows = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {table}
        WHERE {null_condition}
        """
    ).fetchone()[0]

    duplicate_stats = connection.execute(
        f"""
        SELECT
            COUNT(*) AS key_groups,

            COUNT(*) FILTER (
                WHERE group_count > 1
            ) AS duplicate_key_groups,

            COALESCE(
                SUM(group_count - 1) FILTER (
                    WHERE group_count > 1
                ),
                0
            ) AS duplicate_key_rows

        FROM (
            SELECT COUNT(*) AS group_count
            FROM {table}
            GROUP BY {columns}
        ) grouped_keys
        """
    ).fetchone()

    key_groups, duplicate_groups, duplicate_rows = (
        duplicate_stats
    )

    return {
        "dataset": dataset,
        "row_count": row_count,
        "candidate_key": " + ".join(candidate_key),
        "distinct_key_combinations": key_groups,
        "duplicate_key_groups": duplicate_groups,
        "duplicate_key_rows": duplicate_rows,
        "null_key_rows": null_key_rows,
        "unique_candidate_key": (
            duplicate_groups == 0
            and null_key_rows == 0
        ),
    }


# --------------------------------------------------
# Main execution
# --------------------------------------------------

def main() -> None:
    """Run grain and candidate key assessment."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    print("\nDATA GRAIN AND CANDIDATE KEY ASSESSMENT")
    print("=" * 75)

    with duckdb.connect(":memory:") as connection:

        connection.execute("SET memory_limit = '2GB'")
        connection.execute("SET threads = 2")

        temp_path = str(TEMP_DIR.resolve()).replace("'", "''")

        connection.execute(
            f"SET temp_directory = '{temp_path}'"
        )

        load_source_views(connection)

        for dataset, candidate_keys in CANDIDATE_KEYS.items():

            print(f"\nDATASET: {dataset}")
            print("-" * 75)

            for candidate_key in candidate_keys:

                result = assess_candidate_key(
                    connection,
                    dataset,
                    candidate_key,
                )

                results.append(result)

                print(
                    f"Rows: {result['row_count']:,}"
                )

                print(
                    f"Candidate key: "
                    f"{result['candidate_key']}"
                )

                print(
                    f"Distinct key combinations: "
                    f"{result['distinct_key_combinations']:,}"
                )

                print(
                    f"Duplicate key groups: "
                    f"{result['duplicate_key_groups']:,}"
                )

                print(
                    f"Duplicate key rows: "
                    f"{result['duplicate_key_rows']:,}"
                )

                print(
                    f"Rows with null key values: "
                    f"{result['null_key_rows']:,}"
                )

                print(
                    f"Unique candidate key: "
                    f"{result['unique_candidate_key']}"
                )

                print()

        connection.execute(
            """
            CREATE TEMP TABLE grain_results (
                dataset VARCHAR,
                row_count BIGINT,
                candidate_key VARCHAR,
                distinct_key_combinations BIGINT,
                duplicate_key_groups BIGINT,
                duplicate_key_rows BIGINT,
                null_key_rows BIGINT,
                unique_candidate_key BOOLEAN
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO grain_results VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    result["dataset"],
                    result["row_count"],
                    result["candidate_key"],
                    result["distinct_key_combinations"],
                    result["duplicate_key_groups"],
                    result["duplicate_key_rows"],
                    result["null_key_rows"],
                    result["unique_candidate_key"],
                )
                for result in results
            ],
        )

        output_path = str(OUTPUT_PATH.resolve()).replace("'", "''")

        connection.execute(
            f"""
            COPY grain_results
            TO '{output_path}'
            (HEADER, DELIMITER ',')
            """
        )

    print("=" * 75)
    print("GRAIN ASSESSMENT COMPLETE")
    print(f"Results saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

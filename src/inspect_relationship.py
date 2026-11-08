
from pathlib import Path

import duckdb


# --------------------------------------------------
# Project configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "reports"
TEMP_DIR = REPORT_DIR / "duckdb_temp"

RELATIONSHIP_REPORT = REPORT_DIR / "relationship_assessment.csv"
DUPLICATE_REPORT = REPORT_DIR / "duplicate_key_samples.csv"


# --------------------------------------------------
# Source datasets
# --------------------------------------------------

DATASETS = [
    "transaction_data",
    "hh_demographic",
    "product",
    "campaign_desc",
    "campaign_table",
    "coupon",
    "coupon_redempt",
    "causal_data",
]


# Child dataset, parent dataset, and join columns.
RELATIONSHIPS = [
    ("transaction_data", "hh_demographic", ["household_key"]),
    ("transaction_data", "product", ["PRODUCT_ID"]),
    ("campaign_table", "campaign_desc", ["CAMPAIGN"]),
    ("campaign_table", "transaction_data", ["household_key"]),
    ("coupon", "product", ["PRODUCT_ID"]),
    ("coupon", "campaign_desc", ["CAMPAIGN"]),
    ("coupon_redempt", "transaction_data", ["household_key"]),
    ("coupon_redempt", "campaign_desc", ["CAMPAIGN"]),
    ("coupon_redempt", "coupon", ["COUPON_UPC"]),
    ("coupon_redempt", "coupon", ["COUPON_UPC", "CAMPAIGN"]),
    ("causal_data", "product", ["PRODUCT_ID"]),
]


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def register_views(connection):
    """Register all CSV files as temporary DuckDB views."""

    for dataset in DATASETS:
        path = DATA_DIR / f"{dataset}.csv"

        if not path.exists():
            raise FileNotFoundError(path)

        connection.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW
            {quote_identifier(dataset)} AS

            SELECT *
            FROM read_csv_auto(
                '{str(path.resolve())}',
                header = true
            )
            """
        )


def distinct_key_query(dataset, columns):
    """Create a distinct-key query for a dataset."""

    selected = ", ".join(
        quote_identifier(column)
        for column in columns
    )

    return f"""
        SELECT DISTINCT {selected}
        FROM {quote_identifier(dataset)}
        WHERE {" AND ".join(
            f"{quote_identifier(column)} IS NOT NULL"
            for column in columns
        )}
    """


# --------------------------------------------------
# Relationship validation
# --------------------------------------------------

def assess_relationship(connection, child, parent, columns):
    """Measure distinct child keys that match parent keys."""

    child_query = distinct_key_query(child, columns)
    parent_query = distinct_key_query(parent, columns)

    join_condition = " AND ".join(
        f"c.{quote_identifier(column)} = "
        f"p.{quote_identifier(column)}"
        for column in columns
    )

    result = connection.execute(
        f"""
        WITH child_keys AS (
            {child_query}
        ),
        parent_keys AS (
            {parent_query}
        ),
        matches AS (
            SELECT
                COUNT(*) AS matched_keys
            FROM child_keys c
            WHERE EXISTS (
                SELECT 1
                FROM parent_keys p
                WHERE {join_condition}
            )
        )
        SELECT
            (SELECT COUNT(*) FROM child_keys),
            matched_keys
        FROM matches
        """
    ).fetchone()

    total_keys, matched_keys = result

    unmatched_keys = total_keys - matched_keys

    match_rate = (
        matched_keys / total_keys * 100
        if total_keys else 0
    )

    return {
        "child_dataset": child,
        "parent_dataset": parent,
        "join_columns": " + ".join(columns),
        "distinct_child_keys": total_keys,
        "matched_keys": matched_keys,
        "unmatched_keys": unmatched_keys,
        "match_rate_pct": round(match_rate, 2),
    }


# --------------------------------------------------
# Duplicate-key investigation
# --------------------------------------------------

def inspect_duplicate_keys(connection, dataset, columns):
    """Return sample records with repeated candidate keys."""

    group_columns = ", ".join(
        quote_identifier(column)
        for column in columns
    )

    join_condition = " AND ".join(
        f"source.{quote_identifier(column)} = "
        f"duplicates.{quote_identifier(column)}"
        for column in columns
    )

    query = f"""
        WITH duplicates AS (
            SELECT
                {group_columns},
                COUNT(*) AS group_count
            FROM {quote_identifier(dataset)}
            GROUP BY {group_columns}
            HAVING COUNT(*) > 1
            LIMIT 20
        )
        SELECT
            '{dataset}' AS dataset,
            duplicates.group_count,
            source.*
        FROM {quote_identifier(dataset)} source
        INNER JOIN duplicates
            ON {join_condition}
        ORDER BY duplicates.group_count DESC
        LIMIT 100
    """

    return connection.execute(query).fetchall()


# --------------------------------------------------
# Main execution
# --------------------------------------------------

def main():

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(":memory:") as connection:

        connection.execute("SET memory_limit = '2GB'")
        connection.execute("SET threads = 2")

        connection.execute(
            f"SET temp_directory = '{TEMP_DIR.resolve()}'"
        )

        register_views(connection)

        # Relationship checks
        relationship_results = []

        print("\nRELATIONSHIP ASSESSMENT")
        print("=" * 75)

        for child, parent, columns in RELATIONSHIPS:

            result = assess_relationship(
                connection,
                child,
                parent,
                columns,
            )

            relationship_results.append(result)

            print(
                f"\n{child} -> {parent} "
                f"({result['join_columns']})"
            )
            print(
                f"Distinct child keys: "
                f"{result['distinct_child_keys']:,}"
            )
            print(
                f"Matched keys: {result['matched_keys']:,}"
            )
            print(
                f"Unmatched keys: {result['unmatched_keys']:,}"
            )
            print(
                f"Match rate: {result['match_rate_pct']}%"
            )

        connection.execute(
            """
            CREATE TEMP TABLE relationship_results (
                child_dataset VARCHAR,
                parent_dataset VARCHAR,
                join_columns VARCHAR,
                distinct_child_keys BIGINT,
                matched_keys BIGINT,
                unmatched_keys BIGINT,
                match_rate_pct DOUBLE
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO relationship_results VALUES (
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                tuple(result.values())
                for result in relationship_results
            ],
        )

        connection.execute(
            f"""
            COPY relationship_results
            TO '{RELATIONSHIP_REPORT.resolve()}'
            (HEADER, DELIMITER ',')
            """
        )

        # Duplicate-key samples
        print("\nDUPLICATE KEY INVESTIGATION")
        print("=" * 75)

        duplicate_results = []

        duplicate_candidates = {
            "coupon": [
                "COUPON_UPC",
                "PRODUCT_ID",
                "CAMPAIGN",
            ],
            "causal_data": [
                "PRODUCT_ID",
                "STORE_ID",
                "WEEK_NO",
            ],
        }

        for dataset, columns in duplicate_candidates.items():

            rows = inspect_duplicate_keys(
                connection,
                dataset,
                columns,
            )

            duplicate_results.extend(rows)

            print(
                f"\n{dataset}: "
                f"{len(rows)} sample rows retrieved"
            )

            for row in rows[:10]:
                print(row)

        if duplicate_results:
            column_count = len(duplicate_results[0])

            placeholders = ", ".join(
                "?" for _ in range(column_count)
            )

            connection.execute(
                f"""
                CREATE TEMP TABLE duplicate_samples AS
                SELECT *
                FROM (
                    SELECT
                        CAST(NULL AS VARCHAR) AS dataset,
                        CAST(NULL AS BIGINT) AS group_count
                ) WHERE FALSE
                """
            )

            # Build a report with a consistent schema.
            duplicate_columns = [
                "dataset",
                "group_count",
                "key_1",
                "key_2",
                "key_3",
                "key_4",
                "key_5",
                "key_6",
                "key_7",
                "key_8",
            ]

            connection.execute(
                """
                CREATE TEMP TABLE duplicate_report (
                    dataset VARCHAR,
                    group_count BIGINT,
                    key_1 VARCHAR,
                    key_2 VARCHAR,
                    key_3 VARCHAR,
                    key_4 VARCHAR,
                    key_5 VARCHAR,
                    key_6 VARCHAR,
                    key_7 VARCHAR,
                    key_8 VARCHAR
                )
                """
            )

            
            normalized_rows = []

            for row in duplicate_results:
                values = list(row)

                if len(values) > 10:
                    raise ValueError(
                        f"Expected a maximum of 10 values, got {len(values)}: {row}"
                    )

                # Pad shorter rows with None so every row has 10 values.
                values.extend([None] * (10 - len(values)))

                normalized_rows.append(tuple(values))

            connection.executemany(
                """
                INSERT INTO duplicate_report VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                normalized_rows,
            )

            connection.execute(
                f"""
                COPY duplicate_report
                TO '{DUPLICATE_REPORT.resolve()}'
                (HEADER, DELIMITER ',')
                """
            )

    print("\n" + "=" * 75)
    print("RELATIONSHIP ASSESSMENT COMPLETE")
    print(f"Relationship report: {RELATIONSHIP_REPORT}")
    print(f"Duplicate samples: {DUPLICATE_REPORT}")


if __name__ == "__main__":
    main()


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
# 2. Define referential integrity relationships
# --------------------------------------------------

relationships = [
    {
        "child_table": "transaction_data",
        "child_column": "PRODUCT_ID",
        "parent_table": "product",
        "parent_column": "PRODUCT_ID",
    },
    {
        "child_table": "transaction_data",
        "child_column": "household_key",
        "parent_table": "hh_demographic",
        "parent_column": "household_key",
    },
    {
        "child_table": "campaign_table",
        "child_column": "CAMPAIGN",
        "parent_table": "campaign_desc",
        "parent_column": "CAMPAIGN",
    },
    {
        "child_table": "coupon",
        "child_column": "PRODUCT_ID",
        "parent_table": "product",
        "parent_column": "PRODUCT_ID",
    },
    {
        "child_table": "coupon",
        "child_column": "CAMPAIGN",
        "parent_table": "campaign_desc",
        "parent_column": "CAMPAIGN",
    },
]

assessed_at = datetime.now(timezone.utc).replace(tzinfo=None)

results = []


# --------------------------------------------------
# 3. Referential integrity assessment
# --------------------------------------------------

def quote_identifier(identifier):
    """Safely quote a SQL identifier."""
    return '"' + identifier.replace('"', '""') + '"'


for relationship in relationships:

    child_table = relationship["child_table"]
    child_column = relationship["child_column"]
    parent_table = relationship["parent_table"]
    parent_column = relationship["parent_column"]

    child_table_identifier = quote_identifier(child_table)
    child_column_identifier = quote_identifier(child_column)

    parent_table_identifier = quote_identifier(parent_table)
    parent_column_identifier = quote_identifier(parent_column)

    query = f"""
        SELECT
            COUNT(*) AS total_child_rows,

            COUNT(*) FILTER (
                WHERE p.{parent_column_identifier} IS NOT NULL
            ) AS matched_rows,

            COUNT(*) FILTER (
                WHERE p.{parent_column_identifier} IS NULL
            ) AS unmatched_rows,

            COUNT(*) FILTER (
                WHERE c.{child_column_identifier} IS NULL
            ) AS null_key_rows,

            COUNT(DISTINCT c.{child_column_identifier})
                AS distinct_child_keys,

            COUNT(DISTINCT p.{parent_column_identifier})
                AS matched_distinct_keys,

            COUNT(DISTINCT c.{child_column_identifier}) FILTER (
                WHERE p.{parent_column_identifier} IS NULL
            ) AS unmatched_distinct_keys

        FROM raw.{child_table_identifier} c

        LEFT JOIN raw.{parent_table_identifier} p
            ON c.{child_column_identifier}
             = p.{parent_column_identifier}
    """

    (
        total_child_rows,
        matched_rows,
        unmatched_rows,
        null_key_rows,
        distinct_child_keys,
        matched_distinct_keys,
        unmatched_distinct_keys,
    ) = con.execute(query).fetchone()

    results.append({
        "child_table": child_table,
        "child_column": child_column,
        "parent_table": parent_table,
        "parent_column": parent_column,
        "total_child_rows": total_child_rows,
        "matched_rows": matched_rows,
        "unmatched_rows": unmatched_rows,
        "null_key_rows": null_key_rows,
        "distinct_child_keys": distinct_child_keys,
        "matched_distinct_keys": matched_distinct_keys,
        "unmatched_distinct_keys": unmatched_distinct_keys,
        "validation_rule": (
            "Every non-NULL foreign key in the child table "
            "must have a matching key in the parent table. "
            "NULL foreign keys are reported separately."
        ),
        "assessed_at": assessed_at,
    })


# --------------------------------------------------
# 4. Save assessment results
# --------------------------------------------------

con.execute("CREATE SCHEMA IF NOT EXISTS quality")

con.execute("""
    CREATE OR REPLACE TABLE quality.referential_integrity_results (
        child_table VARCHAR,
        child_column VARCHAR,
        parent_table VARCHAR,
        parent_column VARCHAR,
        total_child_rows BIGINT,
        matched_rows BIGINT,
        unmatched_rows BIGINT,
        null_key_rows BIGINT,
        distinct_child_keys BIGINT,
        matched_distinct_keys BIGINT,
        unmatched_distinct_keys BIGINT,
        validation_rule VARCHAR,
        assessed_at TIMESTAMP
    )
""")

con.executemany(
    """
    INSERT INTO quality.referential_integrity_results
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    [
        (
            row["child_table"],
            row["child_column"],
            row["parent_table"],
            row["parent_column"],
            row["total_child_rows"],
            row["matched_rows"],
            row["unmatched_rows"],
            row["null_key_rows"],
            row["distinct_child_keys"],
            row["matched_distinct_keys"],
            row["unmatched_distinct_keys"],
            row["validation_rule"],
            row["assessed_at"],
        )
        for row in results
    ],
)


# --------------------------------------------------
# 5. Print assessment summary
# --------------------------------------------------

print("\nREFERENTIAL INTEGRITY ASSESSMENT SUMMARY")
print("=" * 120)

summary = con.execute("""
    SELECT
        child_table,
        child_column,
        parent_table,
        parent_column,
        total_child_rows,
        matched_rows,
        unmatched_rows,
        null_key_rows,
        distinct_child_keys,
        matched_distinct_keys,
        unmatched_distinct_keys,

        CASE
            WHEN unmatched_rows = 0
             AND null_key_rows = 0
                THEN 'PASS'
            ELSE 'REVIEW'
        END AS status

    FROM quality.referential_integrity_results

    ORDER BY child_table, child_column
""").fetchdf()

print(summary.to_string(index=False))


# --------------------------------------------------
# 6. Print assessment totals
# --------------------------------------------------

print("\nASSESSMENT TOTALS")
print("=" * 120)

total_checks = len(results)

passed_checks = sum(
    row["unmatched_rows"] == 0
    and row["null_key_rows"] == 0
    for row in results
)

review_checks = total_checks - passed_checks

total_unmatched_rows = sum(
    row["unmatched_rows"]
    for row in results
)

total_null_key_rows = sum(
    row["null_key_rows"]
    for row in results
)

total_unmatched_distinct_keys = sum(
    row["unmatched_distinct_keys"]
    for row in results
)

print(f"Total validation checks          : {total_checks}")
print(f"Passed checks                    : {passed_checks}")
print(f"Checks requiring review          : {review_checks}")
print(f"Total unmatched rows             : {total_unmatched_rows}")
print(f"Total NULL foreign key rows      : {total_null_key_rows}")
print(f"Total unmatched distinct keys    : {total_unmatched_distinct_keys}")

print(
    "\nResults saved to "
    "quality.referential_integrity_results"
)

con.close()

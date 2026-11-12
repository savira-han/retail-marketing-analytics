
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
# 2. Validation specifications
# --------------------------------------------------

EXPECTED_ROW_COUNTS = {
    "campaign_desc": 30,
    "campaign_table": 7208,
    "causal_data": 36786524,
    "coupon": 119384,
    "coupon_redempt": 2318,
    "hh_demographic": 801,
    "product": 92353,
    "transaction_data": 2595732,
}

PRODUCT_NULL_COUNTS = {
    "COMMODITY_DESC": 15,
    "DEPARTMENT": 15,
    "SUB_COMMODITY_DESC": 15,
    "CURR_SIZE_OF_PRODUCT": 30607,
}

NUMERIC_COLUMNS = {
    "campaign_desc": {
        "START_DAY": "INTEGER",
        "END_DAY": "INTEGER",
    },
    "transaction_data": {
        "DAY": "INTEGER",
        "WEEK_NO": "INTEGER",
        "QUANTITY": "DECIMAL(18,4)",
        "SALES_VALUE": "DECIMAL(18,4)",
        "RETAIL_DISC": "DECIMAL(18,4)",
        "COUPON_DISC": "DECIMAL(18,4)",
        "COUPON_MATCH_DISC": "DECIMAL(18,4)",
    },
}

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

REFERENTIAL_RELATIONSHIPS = [
    {
        "child_table": "transaction_data",
        "child_column": "PRODUCT_ID",
        "parent_table": "product",
        "parent_column": "PRODUCT_ID",
        "expected_unmatched_rows": 0,
        "expected_unmatched_keys": 0,
    },
    {
        "child_table": "transaction_data",
        "child_column": "household_key",
        "parent_table": "hh_demographic",
        "parent_column": "household_key",
        "expected_unmatched_rows": 1168429,
        "expected_unmatched_keys": 1699,
    },
    {
        "child_table": "campaign_table",
        "child_column": "CAMPAIGN",
        "parent_table": "campaign_desc",
        "parent_column": "CAMPAIGN",
        "expected_unmatched_rows": 0,
        "expected_unmatched_keys": 0,
    },
    {
        "child_table": "coupon",
        "child_column": "PRODUCT_ID",
        "parent_table": "product",
        "parent_column": "PRODUCT_ID",
        "expected_unmatched_rows": 0,
        "expected_unmatched_keys": 0,
    },
    {
        "child_table": "coupon",
        "child_column": "CAMPAIGN",
        "parent_table": "campaign_desc",
        "parent_column": "CAMPAIGN",
        "expected_unmatched_rows": 0,
        "expected_unmatched_keys": 0,
    },
]

EXPECTED_DISPLAY_VALUES = [
    "0", "1", "2", "3", "4", "5", "6", "7", "9", "A"
]

EXPECTED_MAILER_VALUES = [
    "0", "A", "C", "D", "F", "H", "J", "L", "P", "X", "Z"
]

assessed_at = datetime.now(timezone.utc).replace(tzinfo=None)

results = []


# --------------------------------------------------
# 3. Helper functions
# --------------------------------------------------

def quote_identifier(identifier):
    """Safely quote a SQL identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def add_result(
    category,
    check_name,
    observed_value,
    expected_value,
    passed,
    details=None,
):
    """Add an individual validation result."""

    results.append({
        "category": category,
        "check_name": check_name,
        "observed_value": str(observed_value),
        "expected_value": str(expected_value),
        "status": "PASS" if passed else "FAIL",
        "details": details or "",
        "assessed_at": assessed_at,
    })


def get_row_count(table_name):
    """Return the number of rows in a clean table."""

    query = f"""
        SELECT COUNT(*)
        FROM clean.{quote_identifier(table_name)}
    """

    return con.execute(query).fetchone()[0]


def get_duplicate_excess_rows(table_name, columns):
    """
    Return excess duplicate rows based on the supplied columns.

    Excess duplicate rows = total repeated rows beyond
    the first occurrence of each unique combination.
    """

    column_list = ", ".join(
        quote_identifier(column)
        for column in columns
    )

    query = f"""
        SELECT COALESCE(SUM(duplicate_group_size - 1), 0)
        FROM (
            SELECT COUNT(*) AS duplicate_group_size
            FROM clean.{quote_identifier(table_name)}
            GROUP BY {column_list}
            HAVING COUNT(*) > 1
        )
    """

    return con.execute(query).fetchone()[0]


# --------------------------------------------------
# 4. Check table existence
# --------------------------------------------------

existing_tables = {
    row[0]
    for row in con.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'clean'
          AND table_type = 'BASE TABLE'
    """).fetchall()
}

missing_tables = set(EXPECTED_ROW_COUNTS) - existing_tables

for table_name in EXPECTED_ROW_COUNTS:

    exists = table_name in existing_tables

    add_result(
        "table_integrity",
        f"{table_name}_exists",
        exists,
        True,
        exists,
    )


# Stop further SQL checks if a required clean table is missing.
if missing_tables:

    print("\nVALIDATION STOPPED")
    print("=" * 100)
    print("Missing clean tables:", ", ".join(sorted(missing_tables)))

else:

    # --------------------------------------------------
    # 5. Table integrity
    # --------------------------------------------------

    for table_name, expected_rows in EXPECTED_ROW_COUNTS.items():

        actual_rows = get_row_count(table_name)

        add_result(
            "table_integrity",
            f"{table_name}_row_count",
            actual_rows,
            expected_rows,
            actual_rows == expected_rows,
        )


    # --------------------------------------------------
    # 6. Completeness
    # --------------------------------------------------

    for column_name, expected_nulls in PRODUCT_NULL_COUNTS.items():

        column_identifier = quote_identifier(column_name)

        query = f"""
            SELECT
                COUNT(*) FILTER (
                    WHERE {column_identifier} IS NULL
                ) AS null_rows,

                COUNT(*) FILTER (
                    WHERE {column_identifier} IS NOT NULL
                      AND TRIM({column_identifier}) = ''
                ) AS blank_rows

            FROM clean.product
        """

        null_rows, blank_rows = con.execute(query).fetchone()

        add_result(
            "completeness",
            f"product_{column_name}_null_count",
            null_rows,
            expected_nulls,
            null_rows == expected_nulls,
        )

        add_result(
            "completeness",
            f"product_{column_name}_blank_count",
            blank_rows,
            0,
            blank_rows == 0,
        )


    # --------------------------------------------------
    # 7. Uniqueness
    # --------------------------------------------------

    # Check exact duplicate records across every clean table.

    for table_name in EXPECTED_ROW_COUNTS:

        columns = con.execute(
            f"DESCRIBE clean.{quote_identifier(table_name)}"
        ).fetchall()

        column_names = [column[0] for column in columns]

        duplicate_rows = get_duplicate_excess_rows(
            table_name,
            column_names,
        )

        add_result(
            "uniqueness",
            f"{table_name}_exact_duplicate_rows",
            duplicate_rows,
            0,
            duplicate_rows == 0,
        )

    # Check candidate keys.

    for table_name, key_columns in CANDIDATE_KEYS.items():

        duplicate_rows = get_duplicate_excess_rows(
            table_name,
            key_columns,
        )

        add_result(
            "uniqueness",
            f"{table_name}_candidate_key_duplicates",
            duplicate_rows,
            0,
            duplicate_rows == 0,
        )


    # --------------------------------------------------
    # 8. Validity
    # --------------------------------------------------

    # Validate numeric data types and NULL values.

    for table_name, numeric_columns in NUMERIC_COLUMNS.items():

        for column_name, expected_type in numeric_columns.items():

            actual_type = con.execute("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'clean'
                  AND table_name = ?
                  AND column_name = ?
            """, [table_name, column_name]).fetchone()

            if actual_type is None:

                add_result(
                    "validity",
                    f"{table_name}_{column_name}_data_type",
                    "MISSING",
                    expected_type,
                    False,
                )

                continue

            actual_type = actual_type[0].upper()

            add_result(
                "validity",
                f"{table_name}_{column_name}_data_type",
                actual_type,
                expected_type,
                actual_type == expected_type,
            )

            column_identifier = quote_identifier(column_name)

            null_rows = con.execute(f"""
                SELECT COUNT(*)
                FROM clean.{quote_identifier(table_name)}
                WHERE {column_identifier} IS NULL
            """).fetchone()[0]

            add_result(
                "validity",
                f"{table_name}_{column_name}_null_count",
                null_rows,
                0,
                null_rows == 0,
            )

    # Campaign end day must not precede start day.

    invalid_campaign_dates = con.execute("""
        SELECT COUNT(*)
        FROM clean.campaign_desc
        WHERE START_DAY IS NULL
           OR END_DAY IS NULL
           OR END_DAY < START_DAY
    """).fetchone()[0]

    add_result(
        "validity",
        "campaign_date_order",
        invalid_campaign_dates,
        0,
        invalid_campaign_dates == 0,
    )

    # Transaction time must be a valid HHMM value.

    invalid_transaction_times = con.execute("""
        SELECT COUNT(*)
        FROM clean.transaction_data
        WHERE TRANS_TIME IS NULL
           OR NOT REGEXP_FULL_MATCH(TRANS_TIME, '[0-9]{4}')
           OR TRY_CAST(SUBSTRING(TRANS_TIME, 1, 2) AS INTEGER)
                NOT BETWEEN 0 AND 23
           OR TRY_CAST(SUBSTRING(TRANS_TIME, 3, 2) AS INTEGER)
                NOT BETWEEN 0 AND 59
    """).fetchone()[0]

    add_result(
        "validity",
        "transaction_time_HHMM",
        invalid_transaction_times,
        0,
        invalid_transaction_times == 0,
    )

    # Validate causal display values.

    invalid_display_values = con.execute("""
        SELECT COUNT(*)
        FROM clean.causal_data
        WHERE display IS NULL
           OR display NOT IN (
               '0', '1', '2', '3', '4',
               '5', '6', '7', '9', 'A'
           )
    """).fetchone()[0]

    add_result(
        "validity",
        "causal_display_allowed_values",
        invalid_display_values,
        0,
        invalid_display_values == 0,
    )

    # Validate causal mailer values.

    invalid_mailer_values = con.execute("""
        SELECT COUNT(*)
        FROM clean.causal_data
        WHERE mailer IS NULL
           OR mailer NOT IN (
               '0', 'A', 'C', 'D', 'F',
               'H', 'J', 'L', 'P', 'X', 'Z'
           )
    """).fetchone()[0]

    add_result(
        "validity",
        "causal_mailer_allowed_values",
        invalid_mailer_values,
        0,
        invalid_mailer_values == 0,
    )


    # --------------------------------------------------
    # 9. Consistency
    # --------------------------------------------------

    # Check populated VARCHAR values for surrounding whitespace.

    for table_name in EXPECTED_ROW_COUNTS:

        columns = con.execute(
            f"DESCRIBE clean.{quote_identifier(table_name)}"
        ).fetchall()

        for column in columns:

            column_name = column[0]
            data_type = column[1]

            if data_type.upper() != "VARCHAR":
                continue

            column_identifier = quote_identifier(column_name)

            inconsistent_rows = con.execute(f"""
                SELECT COUNT(*)
                FROM clean.{quote_identifier(table_name)}
                WHERE {column_identifier} IS NOT NULL
                  AND TRIM({column_identifier}) <> ''
                  AND {column_identifier} <> TRIM({column_identifier})
            """).fetchone()[0]

            add_result(
                "consistency",
                f"{table_name}_{column_name}_whitespace",
                inconsistent_rows,
                0,
                inconsistent_rows == 0,
            )


    # --------------------------------------------------
    # 10. Referential integrity
    # --------------------------------------------------

    for relationship in REFERENTIAL_RELATIONSHIPS:

        child_table = relationship["child_table"]
        child_column = relationship["child_column"]

        parent_table = relationship["parent_table"]
        parent_column = relationship["parent_column"]

        child_column_identifier = quote_identifier(child_column)
        parent_column_identifier = quote_identifier(parent_column)

        query = f"""
            SELECT
                COUNT(*) FILTER (
                    WHERE c.{child_column_identifier} IS NOT NULL
                      AND p.{parent_column_identifier} IS NULL
                ) AS unmatched_rows,

                COUNT(*) FILTER (
                    WHERE c.{child_column_identifier} IS NULL
                ) AS null_key_rows,

                COUNT(DISTINCT c.{child_column_identifier}) FILTER (
                    WHERE c.{child_column_identifier} IS NOT NULL
                      AND p.{parent_column_identifier} IS NULL
                ) AS unmatched_distinct_keys

            FROM clean.{quote_identifier(child_table)} c

            LEFT JOIN clean.{quote_identifier(parent_table)} p
                ON c.{child_column_identifier}
                 = p.{parent_column_identifier}
        """

        (
            unmatched_rows,
            null_key_rows,
            unmatched_distinct_keys,
        ) = con.execute(query).fetchone()

        relationship_name = (
            f"{child_table}_to_{parent_table}_{child_column}"
        )

        add_result(
            "referential_integrity",
            f"{relationship_name}_unmatched_rows",
            unmatched_rows,
            relationship["expected_unmatched_rows"],
            unmatched_rows == relationship["expected_unmatched_rows"],
            (
                "Expected incomplete demographic coverage."
                if relationship["expected_unmatched_rows"] > 0
                else ""
            ),
        )

        add_result(
            "referential_integrity",
            f"{relationship_name}_null_keys",
            null_key_rows,
            0,
            null_key_rows == 0,
        )

        add_result(
            "referential_integrity",
            f"{relationship_name}_unmatched_distinct_keys",
            unmatched_distinct_keys,
            relationship["expected_unmatched_keys"],
            unmatched_distinct_keys
            == relationship["expected_unmatched_keys"],
        )


# --------------------------------------------------
# 11. Save validation results
# --------------------------------------------------

con.execute("CREATE SCHEMA IF NOT EXISTS quality")

con.execute("""
    CREATE OR REPLACE TABLE quality.clean_validation_results (
        category VARCHAR,
        check_name VARCHAR,
        observed_value VARCHAR,
        expected_value VARCHAR,
        status VARCHAR,
        details VARCHAR,
        assessed_at TIMESTAMP
    )
""")

if results:

    con.executemany(
        """
        INSERT INTO quality.clean_validation_results
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["category"],
                row["check_name"],
                row["observed_value"],
                row["expected_value"],
                row["status"],
                row["details"],
                row["assessed_at"],
            )
            for row in results
        ],
    )


# --------------------------------------------------
# 12. Print validation summary
# --------------------------------------------------

print("\nCLEAN DATA VALIDATION SUMMARY")
print("=" * 120)

if results:

    summary = con.execute("""
        SELECT
            category,
            COUNT(*) AS total_checks,
            COUNT(*) FILTER (
                WHERE status = 'PASS'
            ) AS passed_checks,
            COUNT(*) FILTER (
                WHERE status = 'FAIL'
            ) AS failed_checks

        FROM quality.clean_validation_results

        GROUP BY category

        ORDER BY category
    """).fetchall()

    print(
        f"{'Category':<28}"
        f"{'Total Checks':>15}"
        f"{'Passed':>12}"
        f"{'Failed':>12}"
    )

    for row in summary:

        print(
            f"{row[0]:<28}"
            f"{row[1]:>15,}"
            f"{row[2]:>12,}"
            f"{row[3]:>12,}"
        )

    print("\nFAILED VALIDATION CHECKS")
    print("=" * 120)

    failures = con.execute("""
        SELECT
            category,
            check_name,
            observed_value,
            expected_value,
            details

        FROM quality.clean_validation_results

        WHERE status = 'FAIL'

        ORDER BY category, check_name
    """).fetchall()

    if failures:

        for failure in failures:
            print(failure)

    else:
        print("No failed validation checks.")

    total_checks = len(results)

    passed_checks = sum(
        row["status"] == "PASS"
        for row in results
    )

    failed_checks = total_checks - passed_checks

    print("\nOVERALL VALIDATION TOTALS")
    print("=" * 120)

    print(f"Total validation checks : {total_checks}")
    print(f"Passed checks           : {passed_checks}")
    print(f"Failed checks           : {failed_checks}")

    overall_status = "PASS" if failed_checks == 0 else "FAIL"

    print(f"Overall validation      : {overall_status}")

    print(
        "\nResults saved to "
        "quality.clean_validation_results"
    )

else:

    print("No validation results were generated.")


con.close()


# --------------------------------------------------
# 13. Exit status
# --------------------------------------------------

if missing_tables or any(
    row["status"] == "FAIL"
    for row in results
):
    raise SystemExit(1)

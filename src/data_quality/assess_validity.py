
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
# 2. Validation definitions
# --------------------------------------------------

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

CATEGORICAL_DOMAINS = {
    "causal_data": {
        "display": ["0", "1", "2", "3", "4", "5", "6", "7", "9", "A"],
        "mailer": ["0", "A", "C", "D", "F", "H", "J", "L", "P", "X", "Z"],
    }
}


# --------------------------------------------------
# 3. Result collection
# --------------------------------------------------

results = []

assessed_at = datetime.now(timezone.utc).replace(tzinfo=None)


def add_result(
    table_name,
    column_name,
    check_type,
    total_rows,
    invalid_rows,
    validation_rule,
):
    results.append({
        "table_name": table_name,
        "column_name": column_name,
        "check_type": check_type,
        "total_rows": total_rows,
        "invalid_rows": invalid_rows,
        "validation_rule": validation_rule,
        "assessed_at": assessed_at,
    })


# --------------------------------------------------
# 4. Numeric parsing validation
# --------------------------------------------------

for table_name, columns in NUMERIC_COLUMNS.items():

    for column_name, target_type in columns.items():

        query = f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (
                    WHERE NULLIF(TRIM({column_name}), '') IS NOT NULL
                      AND TRY_CAST(TRIM({column_name}) AS {target_type}) IS NULL
                ) AS invalid_rows
            FROM raw.{table_name}
        """

        total_rows, invalid_rows = con.execute(query).fetchone()

        add_result(
            table_name=table_name,
            column_name=column_name,
            check_type="numeric_parsing",
            total_rows=total_rows,
            invalid_rows=invalid_rows,
            validation_rule=f"Nonblank values must be convertible to {target_type}.",
        )


# --------------------------------------------------
# 5. Campaign date ordering validation
# --------------------------------------------------

query = """
    SELECT
        COUNT(*) AS total_rows,
        COUNT(*) FILTER (
            WHERE TRY_CAST(TRIM(END_DAY) AS INTEGER)
                < TRY_CAST(TRIM(START_DAY) AS INTEGER)
        ) AS invalid_rows
    FROM raw.campaign_desc
"""

total_rows, invalid_rows = con.execute(query).fetchone()

add_result(
    table_name="campaign_desc",
    column_name="START_DAY, END_DAY",
    check_type="date_ordering",
    total_rows=total_rows,
    invalid_rows=invalid_rows,
    validation_rule="END_DAY must be greater than or equal to START_DAY.",
)


# --------------------------------------------------
# 6. Transaction time format validation
# --------------------------------------------------

query = """
    SELECT
        COUNT(*) AS total_rows,
        COUNT(*) FILTER (
            WHERE NOT regexp_full_match(TRIM(TRANS_TIME), '^[0-9]{4}$')
               OR TRY_CAST(SUBSTRING(TRIM(TRANS_TIME), 1, 2) AS INTEGER)
                    NOT BETWEEN 0 AND 23
               OR TRY_CAST(SUBSTRING(TRIM(TRANS_TIME), 3, 2) AS INTEGER)
                    NOT BETWEEN 0 AND 59
        ) AS invalid_rows
    FROM raw.transaction_data
"""

total_rows, invalid_rows = con.execute(query).fetchone()

add_result(
    table_name="transaction_data",
    column_name="TRANS_TIME",
    check_type="time_format",
    total_rows=total_rows,
    invalid_rows=invalid_rows,
    validation_rule="TRANS_TIME must contain four digits in valid HHMM format.",
)


# --------------------------------------------------
# 7. Categorical domain validation
# --------------------------------------------------

for table_name, columns in CATEGORICAL_DOMAINS.items():

    for column_name, allowed_values in columns.items():

        allowed_values_sql = ", ".join(
            "'" + value.replace("'", "''") + "'"
            for value in allowed_values
        )

        query = f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (
                    WHERE TRIM({column_name}) NOT IN ({allowed_values_sql})
                ) AS invalid_rows
            FROM raw.{table_name}
        """

        total_rows, invalid_rows = con.execute(query).fetchone()

        add_result(
            table_name=table_name,
            column_name=column_name,
            check_type="categorical_domain",
            total_rows=total_rows,
            invalid_rows=invalid_rows,
            validation_rule=f"Values must belong to: {', '.join(allowed_values)}.",
        )


# --------------------------------------------------
# 8. Save assessment results
# --------------------------------------------------

con.execute("CREATE SCHEMA IF NOT EXISTS quality")

con.execute("""
    CREATE OR REPLACE TABLE quality.validity_results (
        table_name VARCHAR,
        column_name VARCHAR,
        check_type VARCHAR,
        total_rows BIGINT,
        invalid_rows BIGINT,
        validation_rule VARCHAR,
        assessed_at TIMESTAMP
    )
""")

con.executemany(
    """
    INSERT INTO quality.validity_results VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    [
        (
            row["table_name"],
            row["column_name"],
            row["check_type"],
            row["total_rows"],
            row["invalid_rows"],
            row["validation_rule"],
            row["assessed_at"],
        )
        for row in results
    ],
)


# --------------------------------------------------
# 9. Print assessment summary
# --------------------------------------------------

print("\nVALIDITY ASSESSMENT SUMMARY")
print("=" * 90)

summary = con.execute("""
    SELECT
        table_name,
        column_name,
        check_type,
        total_rows,
        invalid_rows,
        CASE
            WHEN invalid_rows = 0 THEN 'PASS'
            ELSE 'REVIEW'
        END AS status
    FROM quality.validity_results
    ORDER BY table_name, check_type, column_name
""").fetchdf()

print(summary.to_string(index=False))

print("\nASSESSMENT TOTALS")
print("=" * 90)

total_checks = len(results)
passed_checks = sum(row["invalid_rows"] == 0 for row in results)
review_checks = total_checks - passed_checks

print(f"Total validation checks : {total_checks}")
print(f"Passed checks           : {passed_checks}")
print(f"Checks requiring review : {review_checks}")
print("\nResults saved to quality.validity_results")

con.close()

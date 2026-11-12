
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
# 2. Define cleaning rules
# --------------------------------------------------

PRODUCT_NULL_COLUMNS = {
    "COMMODITY_DESC",
    "DEPARTMENT",
    "SUB_COMMODITY_DESC",
    "CURR_SIZE_OF_PRODUCT",
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

assessed_at = datetime.now(timezone.utc).replace(tzinfo=None)

results = []


# --------------------------------------------------
# 3. Helper functions
# --------------------------------------------------

def quote_identifier(identifier):
    """Safely quote a SQL identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def get_row_count(table_name, schema_name):
    """Return the number of rows in a table."""
    query = f"""
        SELECT COUNT(*)
        FROM {schema_name}.{quote_identifier(table_name)}
    """
    return con.execute(query).fetchone()[0]


# --------------------------------------------------
# 4. Discover raw tables
# --------------------------------------------------

tables = con.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'raw'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name
""").fetchall()

if not tables:
    raise RuntimeError("No raw tables found. Cleaning process stopped.")


# --------------------------------------------------
# 5. Create clean schema
# --------------------------------------------------

con.execute("CREATE SCHEMA IF NOT EXISTS clean")


# --------------------------------------------------
# 6. Apply cleaning transformations
# --------------------------------------------------

try:

    con.execute("BEGIN TRANSACTION")

    for (table_name,) in tables:

        table_identifier = quote_identifier(table_name)

        columns = con.execute(
            f"DESCRIBE raw.{table_identifier}"
        ).fetchall()

        select_expressions = []

        for column in columns:

            column_name = column[0]
            column_identifier = quote_identifier(column_name)

            expression = column_identifier

            # DQ-01: Normalize blank product attributes to NULL.
            if (
                table_name == "product"
                and column_name in PRODUCT_NULL_COLUMNS
            ):
                expression = (
                    f"NULLIF(TRIM({column_identifier}), '')"
                )

            # DQ-03: Convert validated numeric fields.
            if (
                table_name in NUMERIC_COLUMNS
                and column_name in NUMERIC_COLUMNS[table_name]
            ):
                target_type = NUMERIC_COLUMNS[table_name][column_name]

                expression = (
                    f"CAST({column_identifier} AS {target_type})"
                )

            select_expressions.append(
                f"{expression} AS {column_identifier}"
            )

        select_clause = ",\n".join(select_expressions)

        # DQ-02: Remove exact duplicate coupon records.
        if table_name == "coupon":
            distinct_keyword = "DISTINCT"
        else:
            distinct_keyword = ""

        query = f"""
            CREATE OR REPLACE TABLE clean.{table_identifier} AS

            SELECT {distinct_keyword}
                {select_clause}

            FROM raw.{table_identifier}
        """

        con.execute(query)

        raw_rows = get_row_count(table_name, "raw")
        clean_rows = get_row_count(table_name, "clean")

        removed_rows = raw_rows - clean_rows

        results.append({
            "table_name": table_name,
            "raw_rows": raw_rows,
            "clean_rows": clean_rows,
            "removed_rows": removed_rows,
            "assessed_at": assessed_at,
        })

    # --------------------------------------------------
    # 7. Validate cleaning results
    # --------------------------------------------------

    validation_errors = []

    for result in results:

        table_name = result["table_name"]
        raw_rows = result["raw_rows"]
        clean_rows = result["clean_rows"]
        removed_rows = result["removed_rows"]

        # Only coupon should have fewer rows due to deduplication.
        if table_name != "coupon" and raw_rows != clean_rows:
            validation_errors.append(
                f"{table_name}: expected {raw_rows} rows, "
                f"found {clean_rows}."
            )

        if table_name == "coupon":

            distinct_raw_rows = con.execute("""
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT *
                    FROM raw.coupon
                )
            """).fetchone()[0]

            if clean_rows != distinct_raw_rows:
                validation_errors.append(
                    "coupon: clean row count does not match "
                    "the number of distinct raw records."
                )

            if removed_rows != 5164:
                validation_errors.append(
                    f"coupon: expected 5164 removed rows, "
                    f"found {removed_rows}."
                )

    # Validate numeric column types.
    for table_name, numeric_columns in NUMERIC_COLUMNS.items():

        for column_name, expected_type in numeric_columns.items():

            actual_type = con.execute(f"""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'clean'
                  AND table_name = ?
                  AND column_name = ?
            """, [table_name, column_name]).fetchone()

            if actual_type is None:
                validation_errors.append(
                    f"{table_name}.{column_name}: column not found."
                )
                continue

            if actual_type[0].upper() != expected_type:
                validation_errors.append(
                    f"{table_name}.{column_name}: expected "
                    f"{expected_type}, found {actual_type[0]}."
                )

    # Validate product blanks were normalized.
    for column_name in PRODUCT_NULL_COLUMNS:

        remaining_blanks = con.execute(f"""
            SELECT COUNT(*)
            FROM clean.product
            WHERE {quote_identifier(column_name)} IS NOT NULL
              AND TRIM({quote_identifier(column_name)}) = ''
        """).fetchone()[0]

        if remaining_blanks > 0:
            validation_errors.append(
                f"product.{column_name}: "
                f"{remaining_blanks} blank values remain."
            )

    if validation_errors:
        raise RuntimeError(
            "Cleaning validation failed:\n"
            + "\n".join(validation_errors)
        )

    con.execute("COMMIT")

except Exception:
    con.execute("ROLLBACK")
    raise


# --------------------------------------------------
# 8. Print cleaning summary
# --------------------------------------------------

print("\nDATA CLEANING SUMMARY")
print("=" * 100)

print(
    f"{'Table':<22}"
    f"{'Raw Rows':>15}"
    f"{'Clean Rows':>15}"
    f"{'Removed Rows':>15}"
)

for result in results:

    print(
        f"{result['table_name']:<22}"
        f"{result['raw_rows']:>15,}"
        f"{result['clean_rows']:>15,}"
        f"{result['removed_rows']:>15,}"
    )


# --------------------------------------------------
# 9. Print validation totals
# --------------------------------------------------

print("\nCLEANING VALIDATION")
print("=" * 100)

print(f"Tables processed       : {len(results)}")
print("Row count validation  : PASS")
print("Numeric type validation: PASS")
print("Product blank validation: PASS")
print("Coupon deduplication  : PASS")

print("\nClean tables saved to the clean schema.")

con.close()

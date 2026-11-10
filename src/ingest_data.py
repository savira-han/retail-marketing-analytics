from pathlib import Path
import csv
import re

import duckdb
import pandas as pd


# ==================================================
# Configuration
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data" / "raw"
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "retail_marketing.duckdb"

REPORT_DIR = PROJECT_ROOT / "reports"
SUMMARY_PATH = REPORT_DIR / "ingestion_summary.csv"
COLUMN_REPORT_PATH = REPORT_DIR / "ingestion_columns.csv"

CSV_ENCODING = "utf-8-sig"
NULL_SENTINEL = "__DUCKDB_INGEST_NULL_7F3A91__"


# ==================================================
# Expected Source Datasets
# ==================================================

# Expected values are based on Phase 2 inspection.
# Changes in the source dataset must be reviewed
# before updating this configuration.

EXPECTED_DATASETS = {
    "campaign_desc": {
        "rows": 30,
        "columns": [
            "DESCRIPTION",
            "CAMPAIGN",
            "START_DAY",
            "END_DAY",
        ],
    },

    "campaign_table": {
        "rows": 7208,
        "columns": [
            "DESCRIPTION",
            "household_key",
            "CAMPAIGN",
        ],
    },

    "causal_data": {
        "rows": 36786524,
        "columns": [
            "PRODUCT_ID",
            "STORE_ID",
            "WEEK_NO",
            "display",
            "mailer",
        ],
    },

    "coupon": {
        "rows": 124548,
        "columns": [
            "COUPON_UPC",
            "PRODUCT_ID",
            "CAMPAIGN",
        ],
    },

    "coupon_redempt": {
        "rows": 2318,
        "columns": [
            "household_key",
            "DAY",
            "COUPON_UPC",
            "CAMPAIGN",
        ],
    },

    "hh_demographic": {
        "rows": 801,
        "columns": [
            "classification_1",
            "classification_2",
            "classification_3",
            "HOMEOWNER_DESC",
            "classification_5",
            "classification_4",
            "KID_CATEGORY_DESC",
            "household_key",
        ],
    },

    "product": {
        "rows": 92353,
        "columns": [
            "PRODUCT_ID",
            "MANUFACTURER",
            "DEPARTMENT",
            "BRAND",
            "COMMODITY_DESC",
            "SUB_COMMODITY_DESC",
            "CURR_SIZE_OF_PRODUCT",
        ],
    },

    "transaction_data": {
        "rows": 2595732,
        "columns": [
            "household_key",
            "BASKET_ID",
            "DAY",
            "PRODUCT_ID",
            "QUANTITY",
            "SALES_VALUE",
            "STORE_ID",
            "RETAIL_DISC",
            "TRANS_TIME",
            "WEEK_NO",
            "COUPON_DISC",
            "COUPON_MATCH_DISC",
        ],
    },
}


# ==================================================
# SQL Helpers
# ==================================================

def quote_identifier(name: str) -> str:
    """Safely quote a SQL identifier."""
    return '"' + name.replace('"', '""') + '"'


def sql_string(value: str) -> str:
    """Safely quote a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


# ==================================================
# Source File Validation
# ==================================================

def discover_source_files() -> dict[str, Path]:
    """Find and validate the expected source CSV files."""

    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Source directory not found: {DATA_DIR}"
        )

    files = {
        path.stem: path
        for path in DATA_DIR.glob("*.csv")
        if path.is_file()
    }

    expected_names = set(EXPECTED_DATASETS)
    actual_names = set(files)

    missing = expected_names - actual_names
    unexpected = actual_names - expected_names

    if missing or unexpected:
        raise ValueError(
            f"Source file mismatch. "
            f"Missing: {sorted(missing)}. "
            f"Unexpected: {sorted(unexpected)}."
        )

    return files


def validate_source_header(
    table_name: str,
    path: Path,
) -> list[str]:
    """Check source CSV headers against Phase 2 findings."""

    with path.open(
        "r",
        encoding=CSV_ENCODING,
        newline="",
    ) as file:

        reader = csv.reader(file, strict=True)

        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError(
                f"{table_name}: source CSV is empty."
            )

    if not headers or any(not column.strip() for column in headers):
        raise ValueError(
            f"{table_name}: blank or missing column name."
        )

    if len(headers) != len(set(headers)):
        raise ValueError(
            f"{table_name}: duplicate column names."
        )

    expected_columns = EXPECTED_DATASETS[table_name]["columns"]

    if headers != expected_columns:
        raise ValueError(
            f"{table_name}: source columns differ from "
            f"the expected Phase 2 schema.\n"
            f"Expected: {expected_columns}\n"
            f"Actual: {headers}"
        )

    return headers


# ==================================================
# DuckDB Ingestion
# ==================================================

def load_csv_to_duckdb(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    path: Path,
) -> None:
    """Load a source CSV directly into its raw table."""

    table = f"raw.{quote_identifier(table_name)}"
    csv_path = sql_string(str(path.resolve()))

    connection.execute(
        f"""
        CREATE OR REPLACE TABLE {table} AS

        SELECT *
        FROM read_csv(
            {csv_path},
            header = true,
            delim = ',',
            all_varchar = true,
            nullstr = {sql_string(NULL_SENTINEL)},
            strict_mode = true
        )
        """
    )


# ==================================================
# Ingestion Validation
# ==================================================

def validate_loaded_table(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    expected_columns: list[str],
    expected_rows: int,
) -> dict:
    """Validate the loaded table against source expectations."""

    table = f"raw.{quote_identifier(table_name)}"

    row_count = connection.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    column_info = connection.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'raw'
          AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchall()

    actual_columns = [row[0] for row in column_info]

    if row_count != expected_rows:
        raise ValueError(
            f"{table_name}: expected {expected_rows:,} rows, "
            f"loaded {row_count:,}."
        )

    if actual_columns != expected_columns:
        raise ValueError(
            f"{table_name}: loaded columns do not match "
            "the expected source structure."
        )

    non_varchar = [
        (name, data_type)
        for name, data_type in column_info
        if data_type != "VARCHAR"
    ]

    if non_varchar:
        raise ValueError(
            f"{table_name}: unexpected data types: {non_varchar}"
        )

    return {
        "row_count": row_count,
        "column_info": column_info,
    }


# ==================================================
# Reporting
# ==================================================

def save_reports(
    summary_rows: list[dict],
    column_rows: list[dict],
) -> None:
    """Save ingestion summary and column reports."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(summary_rows).to_csv(
        SUMMARY_PATH,
        index=False,
    )

    pd.DataFrame(column_rows).to_csv(
        COLUMN_REPORT_PATH,
        index=False,
    )


# ==================================================
# Main Ingestion Pipeline
# ==================================================

def run_ingestion() -> None:

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    files = discover_source_files()

    summary_rows = []
    column_rows = []

    current_table = None

    connection = duckdb.connect(str(DATABASE_PATH))

    try:
        connection.execute("BEGIN TRANSACTION")

        connection.execute(
            "CREATE SCHEMA IF NOT EXISTS raw"
        )

        for table_name, config in EXPECTED_DATASETS.items():

            current_table = table_name
            path = files[table_name]

            print(f"\nIngesting: {table_name}")

            headers = validate_source_header(
                table_name,
                path,
            )

            load_csv_to_duckdb(
                connection,
                table_name,
                path,
            )

            result = validate_loaded_table(
                connection,
                table_name,
                headers,
                config["rows"],
            )

            summary_rows.append({
                "table_name": table_name,
                "source_file": path.name,
                "expected_rows": config["rows"],
                "loaded_rows": result["row_count"],
                "column_count": len(headers),
                "status": "success",
                "error": "",
            })

            for position, (column, data_type) in enumerate(
                result["column_info"],
                start=1,
            ):
                column_rows.append({
                    "table_name": table_name,
                    "column_name": column,
                    "column_position": position,
                    "data_type": data_type,
                })

            print(
                f"Successfully loaded "
                f"{result['row_count']:,} rows."
            )

        connection.execute("COMMIT")

    except Exception as error:

        connection.execute("ROLLBACK")

        for row in summary_rows:
            row["status"] = "rolled_back"
            row["error"] = (
                f"Transaction rolled back because "
                f"{current_table} failed."
            )

        summary_rows.append({
            "table_name": current_table,
            "source_file": (
                files[current_table].name
                if current_table in files
                else ""
            ),
            "expected_rows": (
                EXPECTED_DATASETS[current_table]["rows"]
                if current_table in EXPECTED_DATASETS
                else ""
            ),
            "loaded_rows": "",
            "column_count": "",
            "status": "failed",
            "error": str(error),
        })

        save_reports(summary_rows, [])

        raise

    finally:
        connection.close()

    save_reports(summary_rows, column_rows)

    total_rows = sum(
        row["loaded_rows"]
        for row in summary_rows
    )

    print("\n" + "=" * 60)
    print("INGESTION COMPLETED SUCCESSFULLY")
    print("=" * 60)

    print(f"Tables loaded: {len(summary_rows)}")
    print(f"Total rows loaded: {total_rows:,}")
    print(f"Database: {DATABASE_PATH}")
    print(f"Summary report: {SUMMARY_PATH}")
    print(f"Column report: {COLUMN_REPORT_PATH}")


def main() -> None:
    run_ingestion()


if __name__ == "__main__":
    main()
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
CSV_DELIMITER = ","

# This uncommon marker prevents empty CSV fields from being interpreted
# as NULL during source ingestion. The marker is checked before loading.
NULL_SENTINEL = "__DUCKDB_INGEST_NULL_7F3A91__"

# Configure these only after inspecting the real source schemas.
# Keys are table names derived from relative CSV paths.
#
# Example format, NOT an assertion about the dataset:
# TYPE_OVERRIDES = {
#     "example_table": {
#         "verified_date_column": "DATE",
#         "verified_count_column": "BIGINT",
#     }
# }
TYPE_OVERRIDES: dict[str, dict[str, str]] = {}

ALLOWED_TYPES = {
    "VARCHAR",
    "BOOLEAN",
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "FLOAT",
    "REAL",
    "DOUBLE",
    "DATE",
    "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE",
    "DECIMAL",
}

# DECIMAL precision/scale must be specified, e.g. DECIMAL(12, 2).
DECIMAL_PATTERN = re.compile(r"DECIMAL\(\d{1,2},\s*\d{1,2}\)", re.I)

# ==================================================
# Identifiers and file discovery
# ==================================================

def quote_identifier(name: str) -> str:
    """Safely quote a DuckDB schema, table, or column identifier."""
    return '"' + name.replace('"', '""') + '"'

def table_name_from_path(path: Path) -> str:
    """Create a stable table name from a CSV's relative path."""
    relative = path.relative_to(DATA_DIR).with_suffix("")
    name = "__".join(relative.parts).lower()
    name = re.sub(r"[^a-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")

    if not name:
        raise ValueError(f"Could not derive a table name from {path}")

    if name[0].isdigit():
        name = f"table_{name}"

    return name

def discover_csv_files() -> list[Path]:
    """Discover CSV files recursively without following symlinks."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Raw data directory does not exist: {DATA_DIR}"
        )

    if not DATA_DIR.is_dir():
        raise NotADirectoryError(
            f"Expected a directory: {DATA_DIR}"
        )

    files = sorted(
        (
            path
            for path in DATA_DIR.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() == ".csv"
        ),
        key=lambda path: path.as_posix().lower(),
    )

    if not files:
        raise FileNotFoundError(
            f"No CSV files found in {DATA_DIR}"
        )

    # Fail rather than silently overwrite tables with colliding names.
    table_names = [table_name_from_path(path) for path in files]

    if len(table_names) != len(set(table_names)):
        raise ValueError(
            "Multiple CSV files map to the same DuckDB table name. "
            "Review the source directory structure."
        )

    # Reject type configuration entries that cannot match a discovered file.
    configured_tables = set(TYPE_OVERRIDES)
    discovered_tables = set(table_names)
    unknown_tables = configured_tables - discovered_tables

    if unknown_tables:
        raise ValueError(
            f"TYPE_OVERRIDES contains unknown tables: "
            f"{sorted(unknown_tables)}"
        )

    return files

# ==================================================
# Source-file validation
# ==================================================

def validate_csv_source(path: Path) -> dict:
    """
    Validate CSV encoding, headers, row widths, and record count.
    Uses streaming reads rather than loading the full file into memory.
    """
    row_count = 0

    with path.open(
        "r",
        encoding=CSV_ENCODING,
        newline="",
    ) as file:
        reader = csv.reader(
            file,
            delimiter=CSV_DELIMITER,
            strict=True,
        )

        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty.")

        if not headers:
            raise ValueError("CSV header is empty.")

        headers = [header.strip() for header in headers]

        if any(not header for header in headers):
            raise ValueError("CSV contains a blank column name.")

        if len(headers) != len(set(headers)):
            raise ValueError(
                "CSV contains duplicate column names after trimming."
            )

        for row in reader:
            # Match the common CSV convention that completely blank lines
            # are not data records.
            if not row:
                continue

            if len(row) != len(headers):
                raise ValueError(
                    f"CSV record ending at line {reader.line_num} "
                    f"has {len(row)} fields; expected {len(headers)}."
                )

            row_count += 1

    # Protect the source layer from accidentally converting a real source
    # value into NULL through the configured null marker.
    sentinel_bytes = NULL_SENTINEL.encode("utf-8")

    with path.open("rb") as file:
        overlap = b""
        while True:
            block = file.read(1024 * 1024)
            if not block:
                break

            combined = overlap + block

            if sentinel_bytes in combined:
                raise ValueError(
                    "The configured NULL sentinel already occurs in "
                    "the source file. Change NULL_SENTINEL before loading."
                )

            overlap = combined[-len(sentinel_bytes):]

    return {
        "headers": headers,
        "source_row_count": row_count,
    }

# ==================================================
# Type configuration
# ==================================================

def normalize_type(type_name: str) -> str:
    """Validate configured DuckDB types before using them in SQL."""
    normalized = " ".join(type_name.strip().upper().split())

    if normalized in ALLOWED_TYPES:
        return normalized

    if DECIMAL_PATTERN.fullmatch(normalized):
        precision_scale = re.search(
            r"\((\d{1,2}),\s*(\d{1,2})\)",
            normalized,
        )
        precision = int(precision_scale.group(1))
        scale = int(precision_scale.group(2))

        if precision < 1 or precision > 38 or scale > precision:
            raise ValueError(
                f"Invalid DECIMAL precision/scale: {type_name}"
            )

        return f"DECIMAL({precision}, {scale})"

    raise ValueError(
        f"Unsupported or invalid configured DuckDB type: {type_name}"
    )

def validate_type_overrides(
    table_name: str,
    headers: list[str],
) -> dict[str, str]:
    """Validate type overrides against the actual CSV headers."""
    overrides = TYPE_OVERRIDES.get(table_name, {})
    unknown_columns = set(overrides) - set(headers)

    if unknown_columns:
        raise ValueError(
            f"{table_name}: type overrides refer to unknown columns: "
            f"{sorted(unknown_columns)}"
        )

    return {
        column: normalize_type(type_name)
        for column, type_name in overrides.items()
    }

# ==================================================
# DuckDB loading
# ==================================================

def sql_string(value: str) -> str:
    """Escape a string for a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"

def create_source_table(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
    table_name: str,
) -> None:
    """Load a CSV into the source schema without type inference."""
    source_table = f"source.{quote_identifier(table_name)}"
    csv_path = sql_string(str(path.resolve()))

    connection.execute(
        f"""
        CREATE OR REPLACE TABLE {source_table} AS
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

def create_raw_table(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    headers: list[str],
    overrides: dict[str, str],
) -> None:
    """
    Create the typed ingestion table.

    Unconfigured columns remain VARCHAR. Configured casts fail the
    transaction if the source contains incompatible values.
    """
    source_table = f"source.{quote_identifier(table_name)}"
    raw_table = f"raw.{quote_identifier(table_name)}"

    select_expressions = []

    for column in headers:
        quoted_column = quote_identifier(column)

        if column in overrides:
            target_type = overrides[column]
            expression = (
                f"CAST({quoted_column} AS {target_type}) "
                f"AS {quoted_column}"
            )
        else:
            expression = quoted_column

        select_expressions.append(expression)

    connection.execute(
        f"""
        CREATE OR REPLACE TABLE {raw_table} AS
        SELECT {", ".join(select_expressions)}
        FROM {source_table}
        """
    )

def get_table_metrics(
    connection: duckdb.DuckDBPyConnection,
    schema: str,
    table_name: str,
) -> dict:
    """Return row count, column count, and exact duplicate-row count."""
    qualified_table = f"{quote_identifier(schema)}.{quote_identifier(table_name)}"

    row_count = connection.execute(
        f"SELECT COUNT(*) FROM {qualified_table}"
    ).fetchone()[0]

    columns = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ?
          AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema, table_name],
    ).fetchall()

    column_names = [row[0] for row in columns]

    if column_names:
        distinct_tuple = ", ".join(
            quote_identifier(column) for column in column_names
        )

        duplicate_rows = connection.execute(
            f"""
            SELECT COUNT(*) - COUNT(DISTINCT ({distinct_tuple}))
            FROM {qualified_table}
            """
        ).fetchone()[0]
    else:
        duplicate_rows = 0

    return {
        "row_count": int(row_count),
        "column_count": len(column_names),
        "duplicate_rows": int(duplicate_rows),
        "columns": column_names,
    }

# ==================================================
# Reports
# ==================================================

def save_reports(
    summary_rows: list[dict],
    column_rows: list[dict],
) -> None:
    """Write ingestion results to CSV reports."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    summary_columns = [
        "table_name",
        "source_file",
        "source_row_count",
        "source_column_count",
        "source_table_row_count",
        "raw_table_row_count",
        "source_duplicate_rows",
        "raw_duplicate_rows",
        "status",
        "error",
    ]

    detail_columns = [
        "table_name",
        "column_name",
        "source_position",
        "source_type",
        "raw_type",
        "type_override_applied",
    ]

    pd.DataFrame(
        summary_rows,
        columns=summary_columns,
    ).to_csv(SUMMARY_PATH, index=False)

    pd.DataFrame(
        column_rows,
        columns=detail_columns,
    ).to_csv(COLUMN_REPORT_PATH, index=False)

# ==================================================
# Pipeline
# ==================================================

def run_ingestion() -> None:
    """
    Validate all CSVs, load all tables in one transaction, and
    save reports only after a successful database commit.
    """
    files = discover_csv_files()
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Validate all files before changing the database.
    plans = []

    for path in files:
        table_name = table_name_from_path(path)
        source_info = validate_csv_source(path)
        overrides = validate_type_overrides(
            table_name,
            source_info["headers"],
        )

        plans.append({
            "path": path,
            "table_name": table_name,
            "headers": source_info["headers"],
            "source_row_count": source_info["source_row_count"],
            "overrides": overrides,
        })

    summary_rows = []
    column_rows = []

    with duckdb.connect(str(DATABASE_PATH)) as connection:
        connection.execute("BEGIN TRANSACTION")

        try:
            connection.execute("CREATE SCHEMA IF NOT EXISTS source")
            connection.execute("CREATE SCHEMA IF NOT EXISTS raw")

            for plan in plans:
                path = plan["path"]
                table_name = plan["table_name"]
                headers = plan["headers"]
                overrides = plan["overrides"]
                expected_rows = plan["source_row_count"]

                print(f"Ingesting {path.relative_to(PROJECT_ROOT)}")

                create_source_table(connection, path, table_name)

                source_metrics = get_table_metrics(
                    connection, "source", table_name
                )

                if source_metrics["row_count"] != expected_rows:
                    raise ValueError(
                        f"{table_name}: CSV has {expected_rows:,} data "
                        f"records but DuckDB loaded "
                        f"{source_metrics['row_count']:,} rows."
                    )

                if source_metrics["columns"] != headers:
                    raise ValueError(
                        f"{table_name}: loaded column names/order differ "
                        "from the verified source header."
                    )

                create_raw_table(
                    connection,
                    table_name,
                    headers,
                    overrides,
                )

                raw_metrics = get_table_metrics(
                    connection, "raw", table_name
                )

                if raw_metrics["row_count"] != expected_rows:
                    raise ValueError(
                        f"{table_name}: raw table row count does not "
                        "match the source CSV."
                    )

                if raw_metrics["columns"] != headers:
                    raise ValueError(
                        f"{table_name}: raw table columns/order changed."
                    )

                summary_rows.append({
                    "table_name": table_name,
                    "source_file": path.relative_to(
                        PROJECT_ROOT
                    ).as_posix(),
                    "source_row_count": expected_rows,
                    "source_column_count": len(headers),
                    "source_table_row_count": source_metrics["row_count"],
                    "raw_table_row_count": raw_metrics["row_count"],
                    "source_duplicate_rows": source_metrics["duplicate_rows"],
                    "raw_duplicate_rows": raw_metrics["duplicate_rows"],
                    "status": "success",
                    "error": "",
                })

                for position, column in enumerate(headers, start=1):
                    raw_type = connection.execute(
                        """
                        SELECT data_type
                        FROM information_schema.columns
                        WHERE table_schema = 'raw'
                          AND table_name = ?
                          AND column_name = ?
                        """,
                        [table_name, column],
                    ).fetchone()[0]

                    column_rows.append({
                        "table_name": table_name,
                        "column_name": column,
                        "source_position": position,
                        "source_type": "VARCHAR",
                        "raw_type": raw_type,
                        "type_override_applied": column in overrides,
                    })

            connection.execute("COMMIT")

        except Exception:
            connection.execute("ROLLBACK")
            raise

    # Reports are written after the database transaction commits.
    save_reports(summary_rows, column_rows)

    print("\nINGESTION COMPLETE")
    print("=" * 60)
    print(f"CSV files ingested: {len(summary_rows)}")
    print(f"DuckDB database: {DATABASE_PATH}")
    print(f"Summary report: {SUMMARY_PATH}")
    print(f"Column report: {COLUMN_REPORT_PATH}")

    total_rows = sum(
        row["raw_table_row_count"] for row in summary_rows
    )
    print(f"Total rows loaded: {total_rows:,}")

def main() -> None:
    run_ingestion()

if __name__ == "__main__":
    main()
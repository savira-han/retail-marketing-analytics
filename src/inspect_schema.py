
from pathlib import Path
import csv
import json

import duckdb


# --------------------------------------------------
# Project paths and inspection settings
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_DIR = PROJECT_ROOT / "reports"

SCHEMA_REPORT_PATH = REPORT_DIR / "schema_inspection.csv"

SAMPLE_SIZE = 5
TYPE_SAMPLE_SIZE = 20_480


# --------------------------------------------------
# File discovery
# --------------------------------------------------

def get_csv_files() -> list[Path]:
    """Find CSV source files recursively."""

    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Raw data directory not found: {DATA_DIR}"
        )

    files = sorted(
        (
            path
            for path in DATA_DIR.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() == ".csv"
        ),
        key=lambda path: str(path).lower(),
    )

    if not files:
        raise FileNotFoundError(
            f"No CSV files found in {DATA_DIR}"
        )

    return files


# --------------------------------------------------
# Schema inspection
# --------------------------------------------------

def inspect_schema(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
) -> tuple[list[dict], list[tuple]]:

    """Inspect column names, inferred types, and sample records."""

    schema_result = connection.execute(
        """
        DESCRIBE
        SELECT *
        FROM read_csv_auto(
            ?,
            header = true,
            sample_size = ?
        )
        """,
        [str(path.resolve()), TYPE_SAMPLE_SIZE],
    ).fetchall()

    column_profiles = []

    for position, column in enumerate(schema_result, start=1):
        column_profiles.append(
            {
                "file_name": path.name,
                "file_path": path.relative_to(
                    PROJECT_ROOT
                ).as_posix(),
                "column_position": position,
                "column_name": column[0],
                "inferred_type": column[1],
            }
        )

    sample_records = connection.execute(
        """
        SELECT *
        FROM read_csv_auto(
            ?,
            header = true,
            sample_size = ?
        )
        LIMIT ?
        """,
        [
            str(path.resolve()),
            TYPE_SAMPLE_SIZE,
            SAMPLE_SIZE,
        ],
    ).fetchall()

    return column_profiles, sample_records


# --------------------------------------------------
# Reporting
# --------------------------------------------------

def save_schema_report(column_profiles: list[dict]) -> None:
    """Save inspected schemas into a CSV report."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "file_name",
        "file_path",
        "column_position",
        "column_name",
        "inferred_type",
    ]

    with SCHEMA_REPORT_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(column_profiles)


# --------------------------------------------------
# Main execution
# --------------------------------------------------

def main() -> None:
    """Inspect all CSV source files."""

    csv_files = get_csv_files()
    all_column_profiles = []

    print("\nDATASET SCHEMA INSPECTION")
    print("=" * 70)
    print(f"CSV files found: {len(csv_files)}")

    with duckdb.connect(":memory:") as connection:

        for path in csv_files:

            print(f"\nFILE: {path.name}")
            print("-" * 70)

            columns, sample_records = inspect_schema(
                connection,
                path,
            )

            all_column_profiles.extend(columns)

            print(f"Columns: {len(columns)}")

            print("\nSCHEMA")

            for column in columns:
                print(
                    f"{column['column_position']:>3}. "
                    f"{column['column_name']} "
                    f"({column['inferred_type']})"
                )

            column_names = [
                column["column_name"]
                for column in columns
            ]

            print(f"\nSAMPLE RECORDS (up to {SAMPLE_SIZE})")

            print(
                json.dumps(
                    {
                        "columns": column_names,
                        "records": sample_records,
                    },
                    indent=2,
                    default=str,
                )
            )

    save_schema_report(all_column_profiles)

    print("\n" + "=" * 70)
    print("SCHEMA INSPECTION COMPLETE")
    print(
        f"Total columns inspected: "
        f"{len(all_column_profiles)}"
    )
    print(f"Schema report: {SCHEMA_REPORT_PATH}")


if __name__ == "__main__":
    main()

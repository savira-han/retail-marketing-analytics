
from pathlib import Path
import json
import sqlite3
import tempfile

import pandas as pd


# --------------------------------------------------
# Project paths and profiling settings
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_DIR = PROJECT_ROOT / "reports"

FILE_REPORT_PATH = REPORT_DIR / "data_profile_summary.csv"
COLUMN_REPORT_PATH = REPORT_DIR / "data_profile_columns.csv"

CHUNK_SIZE = 100_000
MAX_DISTINCT_VALUES = 100_000
SAMPLE_SIZE = 5


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def get_csv_files() -> list[Path]:
    """Find CSV files recursively in the raw data directory."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Raw data directory not found: {DATA_DIR}\n"
            "Create data/raw/ and extract the dataset there first."
        )

    if not DATA_DIR.is_dir():
        raise NotADirectoryError(
            f"Expected a directory: {DATA_DIR}"
        )

    return sorted(
        (
            path
            for path in DATA_DIR.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() == ".csv"
        ),
        key=lambda path: str(path).lower(),
    )


def json_value(value: object) -> str:
    """Convert a value to JSON-safe text for reporting."""
    if pd.isna(value):
        return "null"

    if hasattr(value, "item"):
        value = value.item()

    return json.dumps(value, ensure_ascii=False, default=str)


def create_file_profile(path: Path) -> tuple[dict, list[dict]]:
    """
    Profile one CSV in chunks to limit memory usage.

    Source files are read only. Duplicate-row counting uses a
    temporary SQLite database so hashes are stored on disk.
    """
    relative_path = path.relative_to(PROJECT_ROOT).as_posix()

    file_profile = {
        "file_path": relative_path,
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "status": "success",
        "row_count": 0,
        "column_count": 0,
        "duplicate_rows": 0,
        "error": "",
    }

    column_stats: dict[str, dict] = {}
    column_order: list[str] = []

    try:
        with tempfile.TemporaryDirectory(prefix="csv_profile_") as temp_dir:
            database_path = Path(temp_dir) / "row_hashes.sqlite"

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE row_hashes (
                        row_hash TEXT PRIMARY KEY,
                        occurrences INTEGER NOT NULL
                    )
                    """
                )

                chunks = pd.read_csv(
                    path,
                    chunksize=CHUNK_SIZE,
                    dtype="string",
                    encoding="utf-8-sig",
                    on_bad_lines="error",
                )

                for chunk in chunks:
                    # Preserve the column order from the CSV header.
                    if not column_order:
                        column_order = list(chunk.columns)
                        file_profile["column_count"] = len(column_order)

                        for column in column_order:
                            column_stats[column] = {
                                "missing_count": 0,
                                "distinct_values": set(),
                                "distinct_limit_reached": False,
                                "sample_values": [],
                            }

                    file_profile["row_count"] += len(chunk)

                    # Count missing values and collect representative values.
                    for column in column_order:
                        stats = column_stats[column]
                        series = chunk[column]

                        stats["missing_count"] += int(series.isna().sum())

                        if len(stats["sample_values"]) < SAMPLE_SIZE:
                            non_missing = series.dropna()
                            remaining = SAMPLE_SIZE - len(
                                stats["sample_values"]
                            )

                            for value in non_missing.iloc[:remaining]:
                                if value not in stats["sample_values"]:
                                    stats["sample_values"].append(value)

                        if not stats["distinct_limit_reached"]:
                            for value in series.dropna().unique():
                                stats["distinct_values"].add(str(value))

                                if (
                                    len(stats["distinct_values"])
                                    >= MAX_DISTINCT_VALUES
                                ):
                                    stats["distinct_limit_reached"] = True
                                    break

                    # Count duplicate rows across the entire file, including
                    # duplicates that appear in different chunks.
                    row_hashes = pd.util.hash_pandas_object(
                        chunk, index=False
                    )

                    hash_counts = (
                        row_hashes.astype("uint64")
                        .astype(str)
                        .value_counts()
                    )

                    connection.executemany(
                        """
                        INSERT INTO row_hashes (row_hash, occurrences)
                        VALUES (?, ?)
                        ON CONFLICT(row_hash)
                        DO UPDATE SET occurrences =
                            occurrences + excluded.occurrences
                        """,
                        [
                            (row_hash, int(count))
                            for row_hash, count in hash_counts.items()
                        ],
                    )

                duplicate_result = connection.execute(
                    """
                    SELECT COALESCE(SUM(occurrences - 1), 0)
                    FROM row_hashes
                    """
                ).fetchone()

                file_profile["duplicate_rows"] = int(duplicate_result[0])

        column_profiles = []

        for column in column_order:
            stats = column_stats[column]
            missing_count = stats["missing_count"]
            row_count = file_profile["row_count"]

            if stats["distinct_limit_reached"]:
                distinct_count = f">={MAX_DISTINCT_VALUES}"
            else:
                distinct_count = len(stats["distinct_values"])

            column_profiles.append(
                {
                    "file_path": relative_path,
                    "column_name": column,
                    "inferred_type": "string",
                    "missing_count": missing_count,
                    "missing_pct": (
                        round(missing_count / row_count * 100, 2)
                        if row_count
                        else 0.0
                    ),
                    "distinct_count": distinct_count,
                    "distinct_count_is_capped": (
                        stats["distinct_limit_reached"]
                    ),
                    "sample_values": json.dumps(
                        stats["sample_values"],
                        ensure_ascii=False,
                    ),
                }
            )

    except Exception as exc:
        file_profile["status"] = "error"
        file_profile["error"] = f"{type(exc).__name__}: {exc}"

        # Do not present incomplete column statistics as a successful profile.
        column_profiles = []

    return file_profile, column_profiles


# --------------------------------------------------
# Reporting
# --------------------------------------------------

def save_reports(
    file_profiles: list[dict],
    column_profiles: list[dict],
) -> None:
    """Save file-level and column-level reports."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    file_columns = [
        "file_path",
        "file_name",
        "file_size_bytes",
        "status",
        "row_count",
        "column_count",
        "duplicate_rows",
        "error",
    ]

    column_columns = [
        "file_path",
        "column_name",
        "inferred_type",
        "missing_count",
        "missing_pct",
        "distinct_count",
        "distinct_count_is_capped",
        "sample_values",
    ]

    pd.DataFrame(
        file_profiles, columns=file_columns
    ).to_csv(FILE_REPORT_PATH, index=False)

    pd.DataFrame(
        column_profiles, columns=column_columns
    ).to_csv(COLUMN_REPORT_PATH, index=False)


def main() -> None:
    """Profile all CSV files and write the results."""
    csv_files = get_csv_files()

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {DATA_DIR}.\n"
            "Check that the dataset has been extracted into data/raw/."
        )

    file_profiles = []
    column_profiles = []

    print("\nDATASET PROFILING")
    print("=" * 60)
    print(f"CSV files found: {len(csv_files)}")

    for path in csv_files:
        print(f"\nProfiling: {path.name}")

        file_profile, columns = create_file_profile(path)
        file_profiles.append(file_profile)
        column_profiles.extend(columns)

        if file_profile["status"] == "success":
            print(
                f"  Rows: {file_profile['row_count']:,} | "
                f"Columns: {file_profile['column_count']} | "
                f"Duplicate rows: {file_profile['duplicate_rows']:,}"
            )
        else:
            print(f"  ERROR: {file_profile['error']}")

    save_reports(file_profiles, column_profiles)

    successful = sum(
        profile["status"] == "success"
        for profile in file_profiles
    )
    failed = len(file_profiles) - successful

    print("\n" + "=" * 60)
    print("PROFILING COMPLETE")
    print(f"Successful files: {successful}")
    print(f"Failed files: {failed}")
    print(f"File summary: {FILE_REPORT_PATH}")
    print(f"Column details: {COLUMN_REPORT_PATH}")

    if failed:
        raise RuntimeError(
            f"{failed} file(s) could not be profiled. "
            "Review the error column in the file summary."
        )


if __name__ == "__main__":
    main()
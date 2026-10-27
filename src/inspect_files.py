
from pathlib import Path
import csv


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_DIR = PROJECT_ROOT / "reports"
REPORT_PATH = REPORT_DIR / "source_file_inventory.csv"


def format_size(size_bytes: int) -> str:
    """Convert file size from bytes to a readable unit."""
    size = float(size_bytes)

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024

    return f"{size_bytes} B"


def inspect_files() -> list[dict]:
    """Inventory files in the raw data directory."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Raw data directory not found: {DATA_DIR}\n"
            "Create data/raw/ and extract the dataset there."
        )

    if not DATA_DIR.is_dir():
        raise NotADirectoryError(
            f"Expected a directory but found: {DATA_DIR}"
        )

    files = sorted(
        (
            path
            for path in DATA_DIR.rglob("*")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: str(path).lower(),
    )

    inventory = []

    for path in files:
        size_bytes = path.stat().st_size

        inventory.append(
            {
                "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "file_name": path.name,
                "extension": path.suffix.lower() or "(no extension)",
                "size_bytes": size_bytes,
                "size_readable": format_size(size_bytes),
                "is_empty": size_bytes == 0,
            }
        )

    return inventory


def save_inventory(inventory: list[dict]) -> None:
    """Save the inventory as a CSV report."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "relative_path",
        "file_name",
        "extension",
        "size_bytes",
        "size_readable",
        "is_empty",
    ]

    with REPORT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(inventory)


def main() -> None:
    """Run the file inventory and display a summary."""
    inventory = inspect_files()
    save_inventory(inventory)

    print("\nSOURCE FILE INVENTORY")
    print("=" * 60)
    print(f"Data directory: {DATA_DIR}")
    print(f"Files found: {len(inventory)}")

    if inventory:
        total_size = sum(item["size_bytes"] for item in inventory)
        empty_files = sum(item["is_empty"] for item in inventory)

        print(f"Total size: {format_size(total_size)}")
        print(f"Empty files: {empty_files}")

        print("\nFiles:")
        for item in inventory:
            status = " [EMPTY]" if item["is_empty"] else ""
            print(
                f"- {item['relative_path']} | "
                f"{item['size_readable']}{status}"
            )
    else:
        print("No files found. Check the dataset extraction location.")

    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()

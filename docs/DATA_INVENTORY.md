# Dataset Inventory

## 1. Source Overview

The project uses the public **dunnhumby – The Complete Journey** dataset. The downloaded source archive is stored in `data/source_archive/`, with the extracted CSV files stored in `data/raw/`.

The extracted dataset contains eight CSV files with a combined size of approximately 808 MB.

## 2. Source Files

| File | Approximate Size |
|---|---:|
| `hh_demographic.csv` | 42 KB |
| `causal_data.csv` | 664 MB |
| `coupon.csv` | 2.7 MB |
| `campaign_table.csv` | 94 KB |
| `coupon_redempt.csv` | 53 KB |
| `product.csv` | 6.1 MB |
| `campaign_desc.csv` | 540 B |
| `transaction_data.csv` | 135 MB |

## 3. Source Archive

| File | Approximate Size | Location |
|---|---:|---|
| `dunnhumby_The-Complete-Journey.zip` | 128 MB | `data/source_archive/` |

The original ZIP archive is retained separately from the extracted CSV files.

## 4. File Management Notes

Two `.DS_Store` files were found in the data directories. These are macOS Finder metadata files and are not part of the analytical dataset.

They will be excluded from data processing and should be ignored by Git.

## 5. Initial Observations

The largest source files are `causal_data.csv` and `transaction_data.csv`. These files may require more careful handling during inspection and profiling to avoid unnecessary memory usage.

The file inventory establishes which source files are available, but their schemas, data grain, relationships, and analytical suitability have not yet been verified.

These will be examined in the subsequent dataset assessment steps.
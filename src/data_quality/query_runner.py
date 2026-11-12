
from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "retail_marketing.duckdb"

con = duckdb.connect(str(DB_PATH), read_only=True)

# Query all completeness results
results = con.execute("""
SELECT
    'transaction_data -> product' AS relationship,
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (
        WHERE p.PRODUCT_ID IS NULL
    ) AS unmatched_rows
FROM clean.transaction_data t
LEFT JOIN clean.product p
    ON t.PRODUCT_ID = p.PRODUCT_ID

UNION ALL

SELECT
    'transaction_data -> hh_demographic',
    COUNT(*),
    COUNT(*) FILTER (
        WHERE h.household_key IS NULL
    )
FROM clean.transaction_data t
LEFT JOIN clean.hh_demographic h
    ON t.household_key = h.household_key

UNION ALL

SELECT
    'campaign_table -> campaign_desc',
    COUNT(*),
    COUNT(*) FILTER (
        WHERE d.CAMPAIGN IS NULL
    )
FROM clean.campaign_table c
LEFT JOIN clean.campaign_desc d
    ON c.CAMPAIGN = d.CAMPAIGN

UNION ALL

SELECT
    'coupon -> product',
    COUNT(*),
    COUNT(*) FILTER (
        WHERE p.PRODUCT_ID IS NULL
    )
FROM clean.coupon c
LEFT JOIN clean.product p
    ON c.PRODUCT_ID = p.PRODUCT_ID

UNION ALL

SELECT
    'coupon -> campaign_desc',
    COUNT(*),
    COUNT(*) FILTER (
        WHERE d.CAMPAIGN IS NULL
    )
FROM clean.coupon c
LEFT JOIN clean.campaign_desc d
    ON c.CAMPAIGN = d.CAMPAIGN;
""").fetchdf()

print(results.to_string(index=False))

con.close()

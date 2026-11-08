# Data Relationships and Grain Assessment

## 1. Purpose

This document records the observed grain, candidate keys, and validated relationships across the eight source datasets in the dunnhumby – The Complete Journey dataset.

The assessment establishes how the datasets relate, identifies key coverage, and highlights potential join risks that must be considered during analytical data modeling.

The findings are based on the source files and validation checks performed during Phase 2.3.

## 2. Dataset Grain and Candidate Keys

The following table summarizes the observed grain and candidate key assessment for each dataset.

| Dataset | Observed grain | Candidate key | Assessment |
|---|---|---|---|
| `transaction_data` | One purchased product line within a basket | `household_key`, `BASKET_ID`, `PRODUCT_ID`, `TRANS_TIME` | Unique |
| `hh_demographic` | One demographic record per household | `household_key` | Unique |
| `product` | One record per product | `PRODUCT_ID` | Unique |
| `campaign_desc` | One record per campaign | `CAMPAIGN` | Unique |
| `campaign_table` | One household-campaign assignment | `household_key`, `CAMPAIGN` | Unique |
| `coupon` | Coupon-product-campaign association | `COUPON_UPC`, `PRODUCT_ID`, `CAMPAIGN` | Not unique |
| `coupon_redempt` | One household coupon redemption record | `household_key`, `DAY`, `COUPON_UPC`, `CAMPAIGN` | Unique |
| `causal_data` | One product-store-week-promotional configuration record | `PRODUCT_ID`, `STORE_ID`, `WEEK_NO`, `display`, `mailer` | Unique |

### 2.1 Key Validation Findings

Six datasets passed their initial candidate key uniqueness tests: `transaction_data`, `hh_demographic`, `product`, `campaign_desc`, `campaign_table`, and `coupon_redempt`.

The `coupon` dataset did not pass its proposed candidate key test. The combination of `COUPON_UPC`, `PRODUCT_ID`, and `CAMPAIGN` produced 1,824 duplicate key groups and 5,164 excess rows. These records require further investigation before the table's grain can be considered fully established.

The `causal_data` dataset initially failed the proposed three-column key test using `PRODUCT_ID`, `STORE_ID`, and `WEEK_NO`.

Additional validation showed that:

- Adding `display` reduced duplicate key groups from 15,245 to 37.
- Adding `mailer` reduced duplicate key groups to 15,140.
- Adding both `display` and `mailer` produced zero duplicate key groups.

The final candidate key is:

`PRODUCT_ID + STORE_ID + WEEK_NO + display + mailer`

The combination was validated against all 36,786,524 records. No null key values or exact duplicate rows were found.

Therefore, the five-column combination is documented as the validated candidate key and observed grain for `causal_data`.

## 3. Relationship Assessment

Relationship validation was performed by comparing distinct non-null key combinations in the referencing dataset against the corresponding identifiers in the related dataset.

The results below represent distinct-key coverage, not full join cardinality.

| Referencing dataset | Related dataset | Join columns | Matched keys | Unmatched keys | Match rate |
|---|---|---|---:|---:|---:|
| `transaction_data` | `hh_demographic` | `household_key` | 801 / 2,500 | 1,699 | 32.04% |
| `transaction_data` | `product` | `PRODUCT_ID` | 92,339 / 92,339 | 0 | 100% |
| `campaign_table` | `campaign_desc` | `CAMPAIGN` | 30 / 30 | 0 | 100% |
| `campaign_table` | `transaction_data` | `household_key` | 1,584 / 1,584 | 0 | 100% |
| `coupon` | `product` | `PRODUCT_ID` | 44,133 / 44,133 | 0 | 100% |
| `coupon` | `campaign_desc` | `CAMPAIGN` | 30 / 30 | 0 | 100% |
| `coupon_redempt` | `transaction_data` | `household_key` | 434 / 434 | 0 | 100% |
| `coupon_redempt` | `campaign_desc` | `CAMPAIGN` | 30 / 30 | 0 | 100% |
| `coupon_redempt` | `coupon` | `COUPON_UPC` | 556 / 556 | 0 | 100% |
| `coupon_redempt` | `coupon` | `COUPON_UPC`, `CAMPAIGN` | 643 / 643 | 0 | 100% |
| `causal_data` | `product` | `PRODUCT_ID` | 68,377 / 68,377 | 0 | 100% |

### 3.1 Relationship Interpretation

**Household demographics**

Only 801 of the 2,500 distinct purchasing households in `transaction_data` are represented in `hh_demographic`.

This indicates partial demographic coverage. Demographic analysis should therefore distinguish between the full purchasing household population and the subset with available demographic information.

**Product relationships**

All product identifiers found in `transaction_data`, `coupon`, and `causal_data` are present in the `product` dataset.

The `PRODUCT_ID` field can therefore be used to connect these datasets to product attributes. The uniqueness of `product.PRODUCT_ID` also supports a many-to-one relationship from product-level transaction records to the product table.

**Campaign relationships**

All campaign identifiers in `campaign_table`, `coupon`, and `coupon_redempt` are present in `campaign_desc`.

This supports the use of `CAMPAIGN` to retrieve campaign descriptions and associated campaign date information.

**Household relationships**

All households recorded in `campaign_table` and `coupon_redempt` are present in `transaction_data`.

This establishes household identifier coverage between these datasets. It does not establish that every transaction can be attributed to a particular campaign or coupon redemption.

**Coupon relationships**

All coupon UPCs and coupon UPC-campaign combinations found in `coupon_redempt` are represented in `coupon`.

However, the `coupon` dataset contains repeated candidate key combinations. Matching coupon identifiers does not guarantee a one-to-one relationship. Coupon mappings must be examined carefully before joining them to transaction records.

**Causal data relationships**

All product identifiers in `causal_data` are present in `product`.

The five-column candidate key establishes the observed record grain, while `PRODUCT_ID` provides the product-level connection to the product dataset.

## 4. Relationship and Join Considerations

Successful key matching does not automatically guarantee that a join preserves the original row count or sales totals.

The following considerations must be addressed during analytical modeling.

| Relationship | Potential issue | Modeling consideration |
|---|---|---|
| `transaction_data` → `hh_demographic` | Partial demographic coverage | Preserve households without demographic records when analyzing the full customer population. |
| `transaction_data` → `product` | Product-level lookup | Joining on the unique product key should not multiply transaction rows. |
| `campaign_table` → `campaign_desc` | Multiple household assignments across campaigns | Preserve the household-campaign assignment grain. |
| `campaign_table` → `transaction_data` | Multiple transactions per household and potentially multiple campaigns per household | Define campaign eligibility and timing before connecting campaign assignments to transactions. |
| `coupon` → `product` | Multiple coupon records may refer to the same product | Validate mapping multiplicity and avoid inflating product-level metrics. |
| `coupon` → `campaign_desc` | Multiple coupon records may belong to the same campaign | Preserve coupon-level detail when required. |
| `coupon_redempt` → `transaction_data` | Multiple transactions may exist for a redeeming household | Match at an appropriate transaction or redemption grain rather than household alone. |
| `coupon_redempt` → `coupon` | Coupon mappings may contain repeated records or multiple products | Validate the mapping before using it to attribute redemptions to products. |
| `causal_data` → `product` | Multiple promotional configurations can exist for a product | Use the product relationship for product attributes, but do not join to transactions using `PRODUCT_ID` alone. |

The `causal_data` dataset also contains `STORE_ID` and `WEEK_NO`, but the supplied source files do not include a separate store reference table or a calendar mapping. Further validation is required before connecting promotional records to transaction records at the store-week level.

## 5. Confirmed Relationships and Dataset Limitations

The assessment establishes the following:

1. Product identifiers have complete coverage across transaction, coupon, and causal datasets.
2. Campaign identifiers have complete coverage across campaign assignment, coupon, and redemption datasets.
3. Household identifiers in campaign assignments and coupon redemptions are represented in transaction data.
4. Household demographic information covers only a subset of purchasing households.
5. The proposed coupon candidate key is not unique and requires further investigation.
6. The five-column candidate key for `causal_data` is unique across all source records.
7. Store and calendar reference datasets are not available among the supplied source files.

The current relationship assessment does not establish every relationship's full cardinality or guarantee that all joins are safe for analytical use. Those properties must be validated when building the analytical data model.

## 6. Implications for Analytical Modeling

The transaction dataset will serve as the primary source for sales and purchasing behavior analysis because it records purchased product lines, household identifiers, basket identifiers, and transaction values.

The product dataset can provide product and category attributes. Household demographics can enrich customer analysis for the subset of households with available demographic records.

Campaign assignment, campaign description, coupon mapping, and coupon redemption datasets will support marketing engagement and promotional analysis. Their different grains must be preserved when combining them with transaction data.

The `causal_data` dataset provides product-store-week promotional configuration information. It can support analysis of promotional activity, but its presence alone does not establish household exposure or incremental sales impact.

All analytical joins must account for key uniqueness, relationship cardinality, timing, and table grain to prevent duplicated records and inflated business metrics.

## 7. Assessment Status

The dataset grain and relationship coverage assessment is complete for the tested relationships.

The `coupon` candidate key and full relationship cardinality remain areas requiring additional validation during data modeling. No source records have been removed or modified as part of this assessment.
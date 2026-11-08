# Data Dictionary

## 1. Overview

This document describes the structure of the eight source datasets from the dunnhumby – The Complete Journey dataset.

The initial schema was inspected using DuckDB. Data types listed below are inferred from the inspection process and should be treated as preliminary until validated.

## 2. Dataset Schemas

### 2.1 Transaction Data — `transaction_data.csv`

**Purpose:** Records household purchasing activity at the product-line level.

| Column | Inferred Type | Description |
|---|---|---|
| `household_key` | BIGINT | Household identifier |
| `BASKET_ID` | BIGINT | Shopping basket identifier |
| `DAY` | BIGINT | Day identifier |
| `PRODUCT_ID` | BIGINT | Product identifier |
| `QUANTITY` | BIGINT | Quantity purchased |
| `SALES_VALUE` | DOUBLE | Recorded sales value |
| `STORE_ID` | BIGINT | Store identifier |
| `RETAIL_DISC` | DOUBLE | Retail discount value |
| `TRANS_TIME` | VARCHAR | Transaction time |
| `WEEK_NO` | BIGINT | Week identifier |
| `COUPON_DISC` | DOUBLE | Coupon discount value |
| `COUPON_MATCH_DISC` | DOUBLE | Coupon match discount value |

### 2.2 Household Demographics — `hh_demographic.csv`

**Purpose:** Contains demographic and household classification attributes.

| Column | Inferred Type | Description |
|---|---|---|
| `classification_1` | VARCHAR | Household classification field; meaning to be verified |
| `classification_2` | VARCHAR | Household classification field; meaning to be verified |
| `classification_3` | VARCHAR | Household classification field; meaning to be verified |
| `HOMEOWNER_DESC` | VARCHAR | Homeownership description |
| `classification_5` | VARCHAR | Household classification field; meaning to be verified |
| `classification_4` | VARCHAR | Household classification field; meaning to be verified |
| `KID_CATEGORY_DESC` | VARCHAR | Household child-category description |
| `household_key` | BIGINT | Household identifier |

### 2.3 Product — `product.csv`

**Purpose:** Contains product attributes and classification information.

| Column | Inferred Type | Description |
|---|---|---|
| `PRODUCT_ID` | BIGINT | Product identifier |
| `MANUFACTURER` | BIGINT | Manufacturer identifier |
| `DEPARTMENT` | VARCHAR | Product department |
| `BRAND` | VARCHAR | Brand classification |
| `COMMODITY_DESC` | VARCHAR | Commodity description |
| `SUB_COMMODITY_DESC` | VARCHAR | Sub-commodity description |
| `CURR_SIZE_OF_PRODUCT` | VARCHAR | Product size description |

### 2.4 Campaign Description — `campaign_desc.csv`

**Purpose:** Contains campaign descriptions and campaign periods.

| Column | Inferred Type | Description |
|---|---|---|
| `DESCRIPTION` | VARCHAR | Campaign description |
| `CAMPAIGN` | BIGINT | Campaign identifier |
| `START_DAY` | BIGINT | Campaign start-day identifier |
| `END_DAY` | BIGINT | Campaign end-day identifier |

### 2.5 Campaign Table — `campaign_table.csv`

**Purpose:** Contains household campaign assignment records.

| Column | Inferred Type | Description |
|---|---|---|
| `DESCRIPTION` | VARCHAR | Campaign assignment description |
| `household_key` | BIGINT | Household identifier |
| `CAMPAIGN` | BIGINT | Campaign identifier |

### 2.6 Coupon — `coupon.csv`

**Purpose:** Contains coupon definitions and their associated products and campaigns.

| Column | Inferred Type | Description |
|---|---|---|
| `COUPON_UPC` | BIGINT | Coupon identifier |
| `PRODUCT_ID` | BIGINT | Associated product identifier |
| `CAMPAIGN` | BIGINT | Associated campaign identifier |

### 2.7 Coupon Redemption — `coupon_redempt.csv`

**Purpose:** Records household coupon redemption activity.

| Column | Inferred Type | Description |
|---|---|---|
| `household_key` | BIGINT | Household identifier |
| `DAY` | BIGINT | Redemption day identifier |
| `COUPON_UPC` | BIGINT | Redeemed coupon identifier |
| `CAMPAIGN` | BIGINT | Associated campaign identifier |

### 2.8 Causal Data — `causal_data.csv`

**Purpose:** Contains product and store-level promotional activity by week.

| Column | Inferred Type | Description |
|---|---|---|
| `PRODUCT_ID` | BIGINT | Product identifier |
| `STORE_ID` | BIGINT | Store identifier |
| `WEEK_NO` | BIGINT | Week identifier |
| `display` | VARCHAR | Display promotion indicator or category; meaning to be verified |
| `mailer` | VARCHAR | Mailer promotion indicator or category; meaning to be verified |

## 3. Initial Data Structure Observations

The source files cover several analytical areas:

- Household purchasing activity and transaction values.
- Household demographic and classification attributes.
- Product and category information.
- Campaign assignments and campaign periods.
- Coupon definitions and redemption activity.
- Store-level product promotion information.

The transaction dataset appears to contain product-line records associated with shopping baskets. This interpretation requires validation through data-grain analysis.

Some household classification fields and promotional indicators require further investigation before their business meanings can be established.

## 4. Data Type Considerations

The inferred types are not necessarily the final analytical types.

Identifiers such as `household_key`, `PRODUCT_ID`, `CAMPAIGN`, and `COUPON_UPC` should be treated as identifiers rather than numerical measures.

Day and week fields are numeric identifiers representing time periods. Their relationship to calendar dates requires further investigation.

The `display` and `mailer` fields are currently inferred as text and should be examined as categorical attributes.

Final data types and transformations will be determined during ingestion and data modeling, based on verified source characteristics.
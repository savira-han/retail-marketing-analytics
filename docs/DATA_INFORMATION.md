# Business Requirements and Data Mapping

## 1. Purpose

This document maps the business requirements defined in `BUSINESS_CONTEXT.md` against the available datasets from the dunnhumby – The Complete Journey.

The objective is to assess whether the available source data can support the intended business analysis, identify data limitations, and establish which analytical questions can be addressed reliably.

The assessment is based on the observed source structures, columns, data grain, and relationships identified during data understanding. Data availability does not automatically imply that a business outcome can be measured or attributed.

## 2. Business Requirements Mapping

| Business Question | Required Information | Available Datasets | Feasibility | Limitations |
|---|---|---|---|---|
| Who are our customers, and what are their purchasing characteristics? | Household attributes, transaction history, and product information | `hh_demographic`, `transaction_data`, `product` | Partially supported | Demographic records cover only a subset of purchasing households. Customer behavior can be analyzed more broadly than demographic characteristics. |
| Which product categories contribute most to sales? | Product-level sales, product identifiers, and category hierarchy | `transaction_data`, `product` | Supported | Sales contribution can be calculated from transaction values and product attributes. Profitability cannot be assessed because product costs and margins are not available. |
| How do purchasing patterns differ across households? | Household identifiers, basket history, purchase quantities, and transaction values | `transaction_data` | Supported | Analysis can cover observed purchasing behavior. It cannot establish customer motivations or purchasing behavior outside the observation period. |
| How are marketing campaigns distributed across households? | Campaign descriptions, campaign periods, and household campaign assignments | `campaign_desc`, `campaign_table` | Supported | Assignment records do not independently establish whether a household received, viewed, or engaged with a campaign. |
| How are coupons associated with products and campaigns? | Coupon identifiers, product associations, and campaign identifiers | `coupon`, `campaign_desc` | Supported with qualifications | The coupon dataset contains repeated records for the candidate key `COUPON_UPC`, `PRODUCT_ID`, and `CAMPAIGN`. Duplicate records require investigation before analytical use. |
| How are coupons redeemed by households? | Household identifiers, redemption dates, coupon identifiers, and campaign identifiers | `coupon_redempt`, `coupon`, `campaign_desc` | Supported | Redemption records show recorded coupon usage, not the complete population of distributed or eligible coupons. |
| How do in-store promotional activities relate to product sales? | Product, store, week, promotional display and mailer information, and transaction records | `causal_data`, `transaction_data`, `product` | Partially supported | The relationship between promotional configurations and transactions requires further validation. The meaning of display and mailer codes is not yet verified. |
| Which marketing campaigns generate the highest return? | Campaign expenditure, campaign-related revenue, and campaign outcomes | `campaign_desc`, `campaign_table`, `coupon_redempt`, `transaction_data` | Not fully supported | Campaign expenditure and a reliable campaign-level revenue attribution method are unavailable. ROI cannot be calculated reliably from the available data alone. |
| Do marketing campaigns generate incremental sales or profit? | Valid treatment and control groups, campaign exposure, sales outcomes, and preferably contribution margin | Available campaign and transaction datasets | Not supported for a defensible causal measurement | The available data does not establish a sufficiently documented experimental design or provide the cost and margin information required to measure incremental profit. |

## 3. Data Coverage and Limitations

### 3.1 Household Demographic Coverage

The `hh_demographic` dataset contains 801 household records, while `transaction_data` contains 2,500 distinct purchasing households.

Consequently, demographic analysis represents only households with available demographic records. Purchasing behavior can still be analyzed across the broader transaction population, but demographic findings should not be generalized to all purchasing households without considering this coverage limitation.

### 3.2 Campaign Measurement

The campaign datasets provide campaign descriptions and household campaign assignments. Coupon redemption records provide additional evidence of recorded coupon usage.

However, campaign assignment does not necessarily establish campaign exposure or engagement. Campaign expenditure is also unavailable.

Therefore, campaign distribution and redemption activity can be analyzed, but campaign ROI and incremental campaign impact cannot be reliably established from these datasets alone.

### 3.3 Coupon Data Integrity

The `coupon` dataset contains 124,548 records. The candidate combination of `COUPON_UPC`, `PRODUCT_ID`, and `CAMPAIGN` has 5,164 excess records from repeated combinations.

These records require further investigation during Data Quality and Preparation. They should not be removed automatically before their meaning and impact on joins and aggregations are understood.

### 3.4 In-Store Promotional Data

The `causal_data` dataset provides promotional configuration information at the product, store, week, display, and mailer level.

Although `transaction_data` also contains product, store, and week information, the relationship between promotional configurations and actual purchasing behavior must be validated before analysis.

The meanings of the display and mailer codes have not yet been verified. Their interpretation should remain provisional until supporting documentation or evidence is available.

### 3.5 Financial Measurement Limitations

The transaction dataset contains sales values and discount-related fields. However, product costs, contribution margins, marketing expenditure, and other relevant operating costs are not available.

Sales performance can therefore be analyzed, but profitability and return on marketing investment cannot be measured reliably.

## 4. Analytical Opportunities

Based on the available data, the project can support the following analytical areas:

| Analytical Area | Supporting Datasets | Potential Analysis |
|---|---|---|
| Customer purchasing behavior | `transaction_data`, `hh_demographic` | Household purchasing frequency, basket behavior, and demographic comparisons where coverage permits |
| Product and category performance | `transaction_data`, `product` | Sales contribution, product mix, and category purchasing patterns |
| Customer growth and retention | `transaction_data` | First observed purchase, repeat purchasing, purchase frequency, and customer activity patterns |
| Campaign distribution | `campaign_desc`, `campaign_table` | Campaign duration, household assignment, and campaign distribution |
| Coupon performance | `coupon`, `coupon_redempt`, `transaction_data` | Coupon redemption activity and related purchasing behavior |
| In-store promotion analysis | `causal_data`, `transaction_data`, `product` | Product sales patterns associated with recorded promotional configurations |

These analytical opportunities describe what the source data may support. Final metric definitions and analytical methods will be established during Data Quality and Preparation, Analytical Data Modeling, and Business Analysis.

## 5. Ingestion Considerations

The source files consist of eight CSV datasets with substantially different sizes and structures.

The largest source is `causal_data`, containing approximately 36.8 million records. `transaction_data` contains approximately 2.6 million records.

The ingestion process should account for these differences in file size and processing requirements. Source records should be preserved in the raw layer, with validation and data preparation performed separately.

Additional structural and data-quality issues identified during profiling will be investigated in the relevant subsequent phases.

## 6. Phase 2 Assessment

The available datasets provide sufficient information to investigate household purchasing behavior, product performance, campaign distribution, coupon redemption, and selected in-store promotional patterns.

However, the data has limitations in demographic coverage, campaign exposure measurement, financial information, and causal measurement. These limitations must be reflected in the analytical scope and interpretation of findings.

The source files, schemas, candidate grains, keys, and relationships have been examined. The remaining work is to preserve these findings in the project documentation and carry the identified ingestion requirements and unresolved data issues into the subsequent phases.

**Conclusion:** The source data is sufficiently understood to proceed with Data Ingestion, provided that the documented limitations and unresolved questions are retained for subsequent validation.
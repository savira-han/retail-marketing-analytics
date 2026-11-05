# Business Requirements

## 1. Business Background

DailyMart is a grocery retailer serving household customers across multiple product categories. Its marketing activities include customer campaigns, coupons, and promotional programs intended to encourage customer engagement and purchases.

As part of the Marketing Analytics function, the objective of this analysis is to develop a clearer understanding of the business's sales performance, household purchasing behavior, product performance, and marketing engagement.

By bringing transaction and marketing-related information into a consistent analytical view, the business can better understand its customers, identify important sales drivers, and make more informed marketing and merchandising decisions.

### Project Objectives

The analysis aims to:

1. Evaluate overall sales performance and purchasing trends.
2. Understand household purchasing behavior and customer contribution.
3. Assess product and category performance.
4. Examine household engagement with marketing and promotional activities.
5. Identify opportunities to support customer growth and improve marketing decisions.

## 2. Business Problems and Questions

The analysis focuses on four business areas. Each area addresses a specific business need and establishes the questions that will guide the investigation.

### 2.1 Sales Performance and Growth

**Business problem**

Management needs a clearer view of sales performance and household purchasing activity over time. Without a consolidated understanding of these trends, it can be difficult to identify meaningful changes in business performance.

**Business questions**

- How has sales performance changed over the observed period?
- How has household purchasing activity changed over time?
- Which periods experienced noticeable increases or decreases in sales?

### 2.2 Customer Purchasing Behavior

**Business problem**

Households may differ in purchasing frequency, spending patterns, and contribution to overall sales. Understanding these differences is important for identifying valuable customer groups and potential retention opportunities.

**Business questions**

- How frequently do households make purchases?
- How much do households contribute to overall sales?
- How do purchasing patterns differ across household groups?
- What proportion of households demonstrate repeat-purchasing behavior?

### 2.3 Product and Category Performance

**Business problem**

Management needs better visibility into how products and categories contribute to sales and household purchasing activity. This information can help identify important product categories and areas that may require further attention.

**Business questions**

- Which product categories contribute most to overall sales?
- Which categories have the highest household participation?
- How do purchasing patterns differ across product categories?
- Which categories show noticeable changes in sales performance over time?

### 2.4 Marketing and Promotional Performance

**Business problem**

DailyMart uses campaigns, coupons, and promotional activities to engage customers. However, understanding household participation and how promotional activity relates to purchasing behavior requires a more structured view of the available marketing data.

**Business questions**

- How many households were assigned to marketing campaigns?
- How does coupon redemption vary across households and products?
- How does purchasing behavior differ between transactions with and without recorded promotional activity?
- Which products or categories are most frequently associated with promotional activity?

## 3. Measurement Framework

The following metrics will guide the analysis. Their final definitions and calculations will be confirmed after the source data has been inspected and validated.

### 3.1 Sales Performance

| Metric | Definition | Measurement |
|---|---|---|
| Total Sales | Total recorded sales value. | Sum of sales value |
| Sales Growth | Percentage change in sales between comparable periods. | (Current Sales − Previous Sales) / Previous Sales × 100 |
| Units Sold | Total quantity of products purchased. | Sum of quantity |
| Total Baskets | Number of distinct shopping transactions. | Count distinct basket identifiers |
| Average Basket Value | Average sales value per shopping basket. | Total Sales / Total Baskets |

### 3.2 Customer Behavior

| Metric | Definition | Measurement |
|---|---|---|
| Active Households | Households with at least one recorded purchase during the period. | Count distinct household IDs |
| Purchase Frequency | Average number of baskets per active household. | Total Baskets / Active Households |
| Average Spend per Household | Average sales generated per active household. | Total Sales / Active Households |
| Repeat Purchase Rate | Share of active households with at least two baskets during the period. | Repeat Households / Active Households × 100 |
| Household Sales Contribution | Share of total sales generated by a household or customer segment. | Household or Segment Sales / Total Sales × 100 |

### 3.3 Product and Category Performance

| Metric | Definition | Measurement |
|---|---|---|
| Category Sales | Total sales attributed to a product category. | Sum of sales value by category |
| Category Sales Contribution | Share of total sales generated by a category. | Category Sales / Total Sales × 100 |
| Category Units Sold | Total quantity sold within a category. | Sum of quantity by category |
| Household Penetration | Share of active households purchasing from a category. | Households Purchasing Category / Active Households × 100 |

### 3.4 Marketing and Promotional Performance

| Metric | Definition | Measurement |
|---|---|---|
| Campaign Assignments | Number of unique households assigned to a campaign. | Count distinct assigned household IDs |
| Campaign Coverage | Share of eligible observed households assigned to a campaign. | Assigned Households / Eligible Households × 100 |
| Coupon Redemptions | Number of recorded coupon redemption events. | Count redemption records |
| Redeeming Households | Number of unique households with recorded coupon redemptions. | Count distinct redeeming household IDs |
| Promotional Sales | Sales associated with recorded promotional activity. | Sum of matched transaction sales |
| Promotional Sales Share | Share of total sales associated with recorded promotional activity. | Promotional Sales / Total Sales × 100 |

## 4. Data Source and Analytical Boundaries

The analysis will use the publicly available **dunnhumby – The Complete Journey** dataset.

DailyMart is a fictional business scenario. The dataset is used as a proxy to demonstrate how real retail transaction and marketing-related data can support business analysis. It does not represent DailyMart's actual company records.

The analysis will follow these principles:

- Metrics will only be finalized when supported by the available data.
- Differences in data coverage, table granularity, and relationships will be considered before combining datasets.
- Campaign assignment, coupon redemption, and promotional activity will be treated as distinct forms of marketing engagement.
- Observed relationships between promotions and purchasing behavior will not automatically be interpreted as causal effects.
- Profitability, marketing ROI, and incremental impact will not be claimed without sufficient financial data and an appropriate measurement methodology.

## 5. Intended Business Contribution

The analysis is intended to give DailyMart's management a more structured understanding of sales performance, customer purchasing behavior, product contributions, and marketing engagement.

The findings will be used to identify relevant business patterns, highlight potential customer and marketing opportunities, and develop practical recommendations supported by evidence.
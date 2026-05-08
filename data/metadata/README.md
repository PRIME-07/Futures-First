# Analytical Orchestration Platform - Synthetic Dataset Metadata

This directory contains the detailed schemas, column descriptions, and event timelines for the synthetic business datasets spanning 5 years (Jan 2019 to Dec 2023).

## 1. Global Event Timelines and Injected Causalities

### 1.1 COVID-19 Digital Shift (2020-2021)
- **Streaming Platform (Domain 1):** Accelerated watch hours (+40%), increased unique viewers (+30%), and reduced churn rate (-30%) as home-bound audiences expanded.
- **Automotive Sales (Domain 2):** Dealership footfall dropped by 48% due to pandemic-related lockdowns. Forced rapid digitization of sales processes (digital order forms, virtual walkthroughs).
- **E-Commerce (Domain 3):** Prompted a sharp acceleration in e-commerce adoption. Mobile and desktop transactions surged, and Apparel return rates rose significantly due to online sizing issues.

### 1.2 Macroeconomic Inflation & Cost Pressure (2022)
- **Streaming Platform (Domain 1):** Triggered a strategic price increase from $9.99 to $11.99 in January 2022. This price hike led to a major churn spike, particularly among customers preferring low-completion formats like Comedy.
- **Automotive Sales (Domain 2):** Led to high-interest rates (rising from 3.2% to 7.2%) and a drop in financing approval rates (from 82% to 58%). Luxury sales declined by 18.5%, while fuel price spikes drove a dramatic EV adoption surge.
- **E-Commerce (Domain 3):** Supply chain disruptions and high fuel costs drove average shipping costs up by 50% (reaching $8.90 on the West Coast). This directly correlated with a massive cart abandonment rate spike (peaking at 78%).

---

## 2. Domain Schema Definitions

### 2.1 Movies / Streaming Domain
- **SQL Tables:**
  - `movies.csv`: Operational database of all movies including title, genre, budget, and language.
  - `streaming_metrics.csv`: Monthly aggregated watch metrics, decay post-release, and churn impact scores.
  - `subscriptions.csv`: Historical active/new subscribers, churn rates, and subscription prices.
  - `regional_engagement.csv`: Regional preferences and engagement scorecards.
- **CSV/Excel files:**
  - `marketing_spend.csv`: Spent on digital ad campaigns.
  - `critic_reviews.csv`: Critic rating and sentiment scores.
  - `content_performance.xlsx`: Detailed regional and genre-based retention and engagement rates.

### 2.2 Automotive Sales Domain
- **SQL Tables:**
  - `car_models.csv`: Brand, category (including SUV, Luxury, EV), launch/discontinuation dates.
  - `monthly_sales.csv`: Monthly aggregated sales, average price, dealership counts, and total revenue.
  - `financing.csv`: Monthly interest rate and financing approval rates across four regions.
  - `dealership_performance.csv`: Showroom footfall, conversion rates, and sales growth.
- **CSV/Excel files:**
  - `fuel_prices.csv`: Monthly regional fuel prices.
  - `ad_spend.csv`: Corporate ad spend and conversion rate by brand.
  - `service_retention.xlsx`: Post-purchase service and parts retention score by segment.

### 2.3 E-Commerce Platform Domain
- **SQL Tables:**
  - `products.csv`: Sourcing region, category, launch/discontinuation dates.
  - `orders.csv`: Orders count, AOV, returns rate, and revenue by product.
  - `customer_metrics.csv`: Platform repeat purchase rate, churn, and session duration.
  - `regional_sales.csv`: Regional e-commerce revenue and mobile vs desktop conversion rates.
- **CSV/Excel files:**
  - `shipping_costs.csv`: Average shipping cost per region.
  - `campaign_ctr.csv`: CTR and impressions of online marketing campaigns.
  - `abandoned_cart.xlsx`: Monthly regional cart abandonment rates.

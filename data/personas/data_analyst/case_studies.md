# Case studies — Sam Okafor (synthetic persona)

source: synthetic · document: case_studies · persona: data_analyst

## data-cs-01 | Sales by region, one report for everyone
Client: drinks distributor, 30 reps · 2023 · fixed price

They emailed 30 separate Excel files every Monday. I built one Power BI report on their ERP
export with row-level security, so each rep sees their own region and managers see all. DAX
measures for year-on-year, rolling 13 weeks and target attainment. Refresh runs at 6am.

## data-cs-02 | Retiring the copy-paste workbook
Client: food bank charity · 2022 · fixed price

A 40-tab workbook fed by hand from three systems. Replaced the manual steps with Power Query so
the monthly update is "drop the new exports in a folder and press refresh". Wrote a one-page
guide for the volunteer who runs it.

## data-cs-03 | Reporting views for an online shop
Client: homeware e-commerce · 2023 · hourly

Wrote a layer of SQL views in their Postgres (orders, repeat customers, margin by product,
refunds) so their BI tool reads clean tables instead of raw ones. Documented every column.

```sql
create view repeat_customers as
select customer_id, count(*) as orders, min(created_at) as first_order
from orders where status = 'paid'
group by customer_id having count(*) > 1;
```

## data-cs-04 | Why are people leaving? HR attrition in Tableau
Client: mid-size call centre · 2022 · fixed price

Joined HR records with shift patterns; turned out attrition clustered around one rota pattern,
not pay. Delivered a Tableau story with the three charts the HR director used in her board pack.

## data-cs-05 | Café stock sheet that orders itself
Client: café group, 4 sites · 2021 · fixed price

Google Sheets with Apps Script: each site enters closing stock, the sheet suggests tomorrow's
order from par levels and emails the supplier list at 8pm.

## data-cs-06 | Weighting a survey properly
Client: NGO · 2023 · fixed price

12,000 responses that over-represented cities. Raked weights on age, region and gender to
census margins in pandas, then produced charts with confidence intervals so nobody over-read
small differences.

## data-cs-07 | Which channel actually sells?
Client: skincare brand · 2024 · hourly

GA4 export in BigQuery joined to Shopify orders. Compared last-click with a simple
position-based model; paid social looked much better once first touches counted. Results in
Looker Studio.

## data-cs-08 | ABC analysis for a pharmacy
Client: independent pharmacy · 2022 · fixed price

Classified 3,000 products by revenue contribution and turnover so they could cut slow stock.
Plain Excel with pivot tables, because that's what the owner uses.

## data-cs-09 | MRR dashboard for a SaaS
Client: B2B SaaS, 8 people · 2023 · hourly

Stripe data into BigQuery, Looker Studio dashboard with MRR, churned MRR, expansion and cohort
retention. Agreed the definitions in writing first, which took longer than building it.

## data-cs-10 | Cleaning a CRM full of duplicates
Client: B2B events company · 2022 · fixed price

Fuzzy-matched 25,000 contacts on name, company and email domain; produced a merge list for the
sales team to approve rather than merging automatically.

## data-cs-11 | Did the new subject lines work?
Client: newsletter publisher · 2023 · fixed price

Analysed an A/B test on open and click rates with proper significance testing and told them the
honest answer: the difference was within noise, run it longer.

## data-cs-12 | Monthly KPI pack on autopilot
Client: logistics SME · 2024 · hourly

Python script pulls from their SQL Server and two spreadsheets, builds charts with matplotlib
and writes a PDF pack. Runs on the first of each month; used to take two days by hand.

## data-cs-13 | Analytics certificate capstone
Course project · 2020

Bike-share usage analysis in R and Tableau as part of the Google Data Analytics certificate.

## data-cs-14 | Excel training for a finance team
Client: property agency · 2023 · fixed price

Two half-day sessions: XLOOKUP, pivot tables, Power Query basics and how not to hard-code
numbers in formulas.

## data-cs-15 | House prices for an estate agent
Client: estate agent · 2022 · fixed price

Linear regression on their past sales (size, rooms, area, condition) to sanity-check asking
prices. Simple, explained coefficient by coefficient.

## data-cs-16 | Public transport delays blog post
Personal · 2024

Analysed a year of open transit data and wrote it up with charts. Mostly for my own portfolio.

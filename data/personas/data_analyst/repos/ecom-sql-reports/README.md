# ecom-sql-reports

source: synthetic · document: repo_readme · persona: data_analyst

Clean reporting views over an online shop's Postgres database, for any BI tool to read.

| View | What it answers |
|---|---|
| `daily_sales` | revenue, orders, average basket per day |
| `repeat_customers` | who ordered more than once and when they started |
| `product_margin` | margin by product after discounts and refunds |
| `refund_reasons` | refunds grouped by reason code |

Every view has a comment per column. Run `psql -f views.sql` to (re)create them.

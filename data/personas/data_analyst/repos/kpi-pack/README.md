# kpi-pack

source: synthetic · document: repo_readme · persona: data_analyst

Monthly KPI PDF for a logistics company: on-time delivery, cost per drop, fleet utilisation,
complaints per 1,000 deliveries.

Pulls from SQL Server and two Google Sheets, draws charts with matplotlib, writes one PDF.
Scheduled with Windows Task Scheduler on the first of the month. Replaced two days of manual
work.

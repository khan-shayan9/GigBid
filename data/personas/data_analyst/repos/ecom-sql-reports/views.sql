-- source: synthetic · persona: data_analyst · repo: ecom-sql-reports
create or replace view daily_sales as
select date_trunc('day', created_at)::date as day,
       count(*) as orders,
       sum(total) as revenue,
       round(avg(total), 2) as avg_basket
from orders
where status = 'paid'
group by 1;

create or replace view product_margin as
select p.sku,
       p.name,
       sum(oi.quantity * (oi.unit_price - oi.discount)) - coalesce(sum(r.amount), 0) as net_sales,
       sum(oi.quantity * p.unit_cost) as cost,
       round(1 - sum(oi.quantity * p.unit_cost)
                 / nullif(sum(oi.quantity * (oi.unit_price - oi.discount)), 0), 3) as margin
from order_items oi
join products p on p.id = oi.product_id
left join refunds r on r.order_item_id = oi.id
group by p.sku, p.name;

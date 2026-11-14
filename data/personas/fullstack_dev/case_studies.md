# Case studies — Diego Marín (synthetic persona)

source: synthetic · document: case_studies · persona: fullstack_dev

## web-cs-01 | Flow Studio: classes, passes and waitlists
Client: yoga studio with two locations · 2023 · fixed price

They were taking bookings over WhatsApp and a spreadsheet. I built a Next.js app with Postgres
(Prisma) where members buy class passes with Stripe, book, cancel up to 6 hours before, and get
moved off the waitlist automatically when someone cancels. The owner manages the timetable from
a small admin page. Emails go out through a queue so a slow mail provider never blocks checkout.

## web-cs-02 | Dashboard for small landlords
Client: property-management startup · 2022 to 2023 · hourly

Django REST backend, React front end, one Postgres database with every query scoped by the
landlord's account. Rent tracking, maintenance tickets with photos, and a monthly PDF statement.
Around 40 landlords use it.

## web-cs-03 | Headless storefront for a clothing brand
Client: independent fashion label · 2024 · fixed price

Next.js on Vercel reading products from the Shopify Storefront API; checkout stays on Shopify.
Product pages are statically generated and revalidated on webhook when stock changes, so the
site stays fast during drops.

## web-cs-04 | Upgrading an old Laravel app
Client: training company · 2022 · hourly

Laravel 5.4 to 10 in steps, with a test suite written first around the parts that handled
payments. Replaced a hand-rolled login with the framework's auth and fixed two SQL injection
holes found along the way.

## web-cs-05 | Where is my order? Live tracking
Client: food delivery startup · 2023 · fixed price

Node + Socket.IO server, riders' phones post GPS every 10 seconds, customers see the rider on a
map. Redis pub/sub so we could run two server instances. Hardest part was dealing with riders in
tunnels and dropped connections without showing them jumping across the city.

```js
// ignore points that imply > 80 km/h between two pings; usually a GPS glitch
if (speedKmh(prev, next) > 80) return;
```

## web-cs-06 | Accessibility pass for a charity site
Client: education charity · 2022 · fixed price

Keyboard navigation, focus states, colour contrast, alt text, form labels, and a skip link.
Went from dozens of axe violations to zero on the main templates and wrote a short guide so
their editors don't reintroduce problems.

## web-cs-07 | Admin panel for a logistics company
Client: regional courier · 2021 · hourly

React-admin on top of their existing REST API: shipments, drivers, depots, CSV imports. Mostly
about permissions — depot managers only see their depot.

## web-cs-08 | Making a news site fast
Client: local news site · 2023 · hourly

Lighthouse mobile score was in the 30s. Image resizing and modern formats, removing two unused
tracking scripts, caching headers on the CDN, lazy-loading comments. Ended in the 90s on
article pages.

## web-cs-09 | Law firm: WordPress to Next.js
Client: law firm · 2024 · fixed price

Content moved to a headless CMS, pages rebuilt in Next.js with the same URLs (redirect map for
the few that changed) so search rankings held.

## web-cs-10 | Syncing invoices to Xero
Client: cleaning services company · 2022 · fixed price

Node service that pushes invoices from their booking tool into Xero and pulls payment status
back, with retries and a dead-letter table for invoices Xero rejects.

## web-cs-11 | Locking down an Express API
Client: fintech prototype · 2023 · hourly

Added TOTP two-factor login, per-IP and per-account rate limiting, Helmet headers, and moved
secrets out of the repo into environment variables.

## web-cs-12 | CI/CD for a three-person startup
Client: B2B SaaS startup · 2024 · hourly

GitHub Actions: lint, type-check, tests, preview deploys per pull request, and Docker images for
the API. Deploys went from "Friday afternoon panic" to merge-and-forget.

## web-cs-13 | MERN to-do app
Bootcamp project · 2018

MongoDB, Express, React, Node. The classic. Kept here because it was my first full-stack app.

## web-cs-14 | Chrome extension for a recruiter
Client: solo recruiter · 2021 · fixed price

Small extension that saves a candidate's public profile fields into a Google Sheet with one
click.

## web-cs-15 | Checkout redesign on mobile
Client: home goods shop · 2023 · fixed price

Rebuilt the checkout from five steps to two on mobile, with address autocomplete and clearer
errors. Worked from the client's Figma; abandoned carts went down in their analytics.

## web-cs-16 | Open-source fix in a date picker
Personal · 2022

Fixed a timezone bug where dates shifted by a day for users west of UTC; the PR was merged
upstream.

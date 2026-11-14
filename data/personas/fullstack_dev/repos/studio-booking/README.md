# studio-booking

source: synthetic · document: repo_readme · persona: fullstack_dev

Class booking for small fitness studios: timetable, passes, Stripe checkout, waitlists.

## Stack
Next.js App Router, Prisma + Postgres, Stripe Checkout and webhooks, a tiny job queue for
emails.

## Waitlist rule
When a booking is cancelled more than 6 hours before class, the first person on the waitlist is
booked and emailed. Inside 6 hours the spot just opens up.

## Dev
```bash
cp .env.example .env   # STRIPE_SECRET_KEY, DATABASE_URL
npx prisma migrate dev
npm run dev
```

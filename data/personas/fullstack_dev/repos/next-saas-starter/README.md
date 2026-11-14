# next-saas-starter

source: synthetic · document: repo_readme · persona: fullstack_dev

What I copy into every new SaaS client project.

- Next.js + TypeScript strict, Tailwind
- Auth with sessions, team accounts, every query scoped by `teamId`
- GitHub Actions: lint, type-check, test, preview deploy per PR
- Dockerfile for the API, health check route

The middleware below blocks requests without a session and adds the team id to the request.

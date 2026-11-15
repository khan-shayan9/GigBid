# MCP Tool Inventory

GigBid's agents reach every external system through MCP tools, via `agent/mcp_client.py`. Each
node gets only the tools in its allowlist (`mcp.allowlists` in `agent/config.yaml`). The exact
input and output schemas and annotations are pinned in `tests/contract/snapshots/`; CI fails on
any unintended change. How to run each server is in `docs/RUNBOOK.md`.

## Our tools

Annotations: `ro` = readOnlyHint, `destr` = destructiveHint, `idem` = idempotentHint,
`open` = openWorldHint.
- Every write takes an `idempotency_key` and a `dry_run` flag that defaults to `true`.
- Real writes run only after an approved `interrupt()`.
- Auth: over HTTP, a per-user Bearer token from `<SERVER>_MCP_TOKENS`, and the endpoint will not
  start without tokens. Over stdio, the session is one local user (`<SERVER>_STDIO_USER`). The
  user always comes from the session, never from a tool argument.

| Tool | Server | Read / write | Annotations | Auth |
|---|---|---|---|---|
| `search_jobs` | marketplace (8082) | read | ro, open | Bearer `MARKETPLACE_MCP_TOKENS`; rate limit; audit log |
| `get_job` | marketplace | read | ro, open | same |
| `get_client_history` | marketplace | read | ro, open | same |
| `get_connects_balance` | marketplace | read | ro, open | same |
| `get_market_rates` | marketplace | read | ro, open | same |
| `list_messages` | marketplace | read | ro, open | same |
| `list_proposals` | marketplace | read (proposals and their lifecycle status, for the pipeline board) | ro, open | same |
| `create_proposal_draft` | marketplace | write (draft, no cost) | not ro, not destr, idem, open | same, plus approved interrupt |
| `submit_proposal` | marketplace | write (spends Connects) | not ro, destr, idem, open | same, plus approved interrupt |
| `send_message` | marketplace | write (to client) | not ro, not destr, idem, open | same, plus approved interrupt |
| `search_evidence` | portfolio (8083) | read | ro, not open | Bearer `PORTFOLIO_MCP_TOKENS` |
| `get_case_study` | portfolio | read | ro, not open | same |
| `list_skills` | portfolio | read | ro, not open | same |
| `find_free_slots` | workspace (8084) | read | ro, not open | Bearer `WORKSPACE_MCP_TOKENS` |
| `hold_slot` | workspace | write (tentative hold) | not ro, not destr, idem, not open | same, plus approved interrupt |
| `draft_email` | workspace | write (draft only, never sent) | not ro, not destr, idem, not open | same, plus approved interrupt |

Portfolio also serves the resources `portfolio://case/{case_id}` and
`portfolio://proposal/{proposal_id}`, and the prompts `draft_proposal` and `map_requirements`.

**What each server does:**
- **Marketplace:** GigSim, or live Upwork, behind `MarketplacePort`.
  - Rate limit: `MARKETPLACE_RATE_PER_MINUTE` per user (default 20).
  - GigSim 429s (after `Retry-After`) and 5xx errors are retried, four tries in all, then the
    tool returns `marketplace_unavailable`.
  - Audit log: append-only JSONL, PII masked, with user, tool, arguments, result and trace id.
  - In live mode `submit_proposal` and `send_message` refuse (`submit_on_upwork`,
    `send_on_upwork`), because live mode only creates drafts.
- **Portfolio:** read-only, over `data/personas/<user>/` only.
  - Each user sees only their own files (tested).
  - Search runs the retrieval variant set in `rag.variant` (`rag/retriever.py`, ADR 0005)
    over fixed chunks; results are whole evidence items, so cited ids stay item ids.
  - Items carry metadata: persona, type, project, skills, date, client industry, outcome.
  - Past proposals are opt-in in `search_evidence`.
- **Workspace:** a local mock.
  - Working hours are weekdays in the user's timezone.
  - Holds and drafts live in `data/processed/workspace/`; overlapping holds are refused.

**Why only Marketplace has a rate limiter and audit log:** it is the only server that reaches an
external, rate-limited system, and the only one that can spend money or contact a client.
Portfolio is read-only over the user's own files, and Workspace writes only local drafts and
holds.

**MCP Inspector screenshots (A7)**, each showing the tool list and one call:
- Marketplace: `docs/images/inspector-marketplace-tools.jpeg` and `inspector-marketplace-call.jpeg`
- Portfolio: `docs/images/inspector-portfolio-tools.jpeg` and `inspector-portfolio-call.jpeg`
- Workspace: `docs/images/inspector-workspace-tools.png` and `inspector-workspace-call.jpeg`

## Per-node allowlists (A6)

| Node | Tools |
|---|---|
| scout | `search_jobs` |
| analyst, compliance | none |
| risk_assessor | `get_job`, `get_client_history` |
| pricing | `get_job`, `get_client_history`, `get_market_rates`, `get_connects_balance` |
| fit_matcher | `search_evidence`, `get_case_study`, `list_skills` |
| writer, verifier, critic | `search_evidence`, `get_case_study` |
| client_liaison | `list_messages`, `find_free_slots`, `hold_slot`, `draft_email`, `send_message` |
| submitter | `create_proposal_draft` (`dry_run=true` for the approval preview), then `create_proposal_draft` and `submit_proposal` for real only after an approved interrupt |
| web (the API's own reads, Phase 6) | `get_job`, `list_proposals`, `list_messages`, `get_connects_balance` |
| github_ingest (Phase 4 ingestion) | `search_repositories`, `get_file_contents`, `list_commits` |

How the client handles failures:
- Every call has a timeout (`mcp.timeout_s`), including calls a model makes through
  `tools_for()`.
- Only read-only tools, and writes that carry an idempotency key, are retried.
- A server that is down raises `ToolUnavailable` (degraded mode); a refusal raises `ToolFailed`.
- When two servers expose the same tool name, the first registration wins, so a third-party
  server cannot shadow our tools.

## Third-party servers and why we trust them (A5)

| Tool | Server | Read / write | Annotations | Auth |
|---|---|---|---|---|
| `search_repositories`, `get_file_contents`, `list_commits` (13 repo tools exposed) | GitHub MCP (hosted) | read | ro (all 13, checked live) | fine-grained PAT, read-only, public repos (`GITHUB_PERSONAL_ACCESS_TOKEN`) |
| Upwork tools (names known only after sign-in) | Upwork MCP (official) | read, and drafts only | per Upwork | OAuth 2.1 per user; tokens encrypted at rest |

### Upwork MCP (official), live mode
- **What:** `https://mcp.upwork.com/mcp`, hosted by Upwork. It is an OAuth 2.1 protected resource
  (PKCE S256, dynamic client registration; authorize and token endpoints on `www.upwork.com`).
  We checked this against its `/.well-known` metadata on 2026-11-15.
- **Why trust it:** it is Upwork's own server for Upwork's own data, so it is the platform-sanctioned
  path. The alternative, scraping, is out of scope and against Upwork's terms.
- **Containment:**
  - The adapter is reached only through `MarketplacePort`.
  - Live mode never submits or sends; it only creates drafts that the user confirms on Upwork.
  - Each user's tokens are Fernet-encrypted at rest (`apps/api/auth/token_store.py`,
    `TOKEN_ENCRYPTION_KEY`) and never logged.
  - Without stored tokens, a call fails with `upwork_login_required` before any network request.
  - Each GigBid tool is mapped to an Upwork tool in config (`marketplace.upwork_live.tools`), and
    an unmapped call fails with `not_mapped`.
- **Status:** the adapter and token store are built and tested with fakes. A real sign-in is a
  user-owned task (`python -m mcp_servers.marketplace.adapters.upwork_live login --user <user>`
  prints Upwork's tool list). Live mode returns no valid results until the tool map and field
  mapping are filled in after that sign-in.

### GitHub MCP (official, hosted)
- **What:** `https://api.githubcopilot.com/mcp/`, run by GitHub. We call it with headers
  `X-MCP-Toolsets: repos` and `X-MCP-Readonly: true`, which expose 13 repository tools, all
  read-only (checked live on 2026-11-15).
- **Why trust it:** it is GitHub's own server over GitHub's own API, maintained by GitHub.
- **Containment:**
  - A fine-grained personal access token with read-only access to public repositories.
  - The server's read-only mode and toolset filter.
  - Our own `github_ingest` allowlist of three tools.
  - Fetched README and code text is treated as untrusted data in prompts, like job posts.

## R&D A: does tool granularity change agent behaviour?

**Hypothesis:** few coarse tools save tokens but hurt tool selection and arguments. A small,
role-specific set of fine-grained tools with rewritten descriptions is the most accurate and
almost as cheap as coarse.

**Setup** (`evals/runners/rnd_a_tool_granularity.py`):
- **Tasks:** 40 tasks with known correct calls (`evals/datasets/rnd_a_tool_tasks.jsonl`). They
  cover all 15 of our tools and include preview-versus-approved writes.
- **Model:** `openai/gpt-oss-20b` (the small model of the `open` profile) on Groq.
- **Scoring:** only the first tool call is scored; nothing is executed.
- **Tool sets:**
  - **fine:** all 15 tools, as shipped;
  - **coarse:** one tool per server, with an `action` enum and an `arguments` object;
  - **allowlisted:** only the task node's tools (an ablation);
  - **best:** allowlisted, with rewritten tool and argument descriptions
    (`evals/datasets/rnd_a_best_descriptions.json`).

**Results** (one run, 2026-11-15; source:
`evals/results/rnd_a_tool_granularity_openai_gpt-oss-20b.json`, per task in the `.csv`):

| Tool set | Tool selection | Arguments, given right tool | End to end | Tokens per task | Invalid calls |
|---|---|---|---|---|---|
| fine (15 tools) | 0.95 | 0.947 | 0.90 | 2104 | 0 |
| coarse (3 tools) | 0.85 | 0.882 | 0.75 | 953 | 4 |
| allowlisted | 1.00 | 0.80 | 0.80 | 680 | 0 |
| best | 0.975 | 0.974 | 0.95 | 763 | 0 |

**What the results show:**
- **Coarse was the least accurate.** The model invented tool names such as `workspace.run` (4 calls
  rejected by the provider) and picked wrong actions.
- **Allowlisting alone cut tokens by about two thirds against fine,** but its end-to-end score fell
  from 0.90 to 0.80. Its errors were omissions:
  - after an approval, it left `dry_run` at its default `true`;
  - it left out search filters or the query;
  - it changed one idempotency key.
  
  Some of the gap to fine may be sampling noise: the runs set no temperature, and the per-task
  differences go both ways.
- **Best fixed those omissions.** It used about 36% of fine's tokens, and its two failures were
  `list_skills` mistaken for `search_evidence` (a20) and one approved hold left as a preview (a30).

**Conclusion:**
- Granularity mattered. Merging tools into coarse dispatchers cost accuracy. Narrowing each node to
  its own tools cut tokens most, but needed better descriptions to keep argument accuracy.
- We ship fine-grained tools behind per-node allowlists. The rewritten descriptions are a
  candidate for the servers' docstrings: adopting them changes the contract snapshots, so they
  are proposed as their own change.
- Whatever the descriptions say, the graph's submit step sets `dry_run` and the idempotency key
  itself after the approved `interrupt()`, never a model.

**Limits:**
- One model and one run of 40 tasks; a difference of one or two tasks is within noise.
- We wrote the tasks ourselves.
- The best descriptions were written after seeing the failures on these same tasks, so best's
  score is optimistic. A fresh task set is needed to confirm it.
- The expected tool is always inside the node's allowlist by construction, and the scout's
  allowlist has one tool, so its four tasks cannot fail selection in the allowlisted and best
  sets.
- Only the first call is scored.

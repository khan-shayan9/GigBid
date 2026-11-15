FastAPI backend for the web app. `routers/` define endpoints, `schemas/` the typed request and
response models, `services/` the use cases (runs, inbox, messages, profiles, insights),
`streaming.py` the SSE bridge, `runtime.py` the shared checkpointer, store, graphs and MCP/model
factories, and `auth/` the accounts, sessions and encrypted OAuth token store.

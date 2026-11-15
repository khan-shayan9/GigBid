Contract tests. `test_mcp_tool_schemas.py` snapshots every MCP tool's description, input and
output schema and annotations, and every resource template and prompt, in `snapshots/`. It fails
CI on unintended changes. Accept an intended change with
`UPDATE_SNAPSHOTS=1 uv run pytest tests/contract` and commit the snapshot.

"""R&D A: does tool granularity change tool-selection accuracy, argument accuracy and tokens?

Tool sets over the same 40 tasks (evals/datasets/rnd_a_tool_tasks.jsonl), one model:
- fine: all 15 tools of our three MCP servers, as shipped;
- coarse: one tool per server with an `action` enum and an `arguments` object;
- allowlisted: the fine tools in the task's node allowlist (agent/config.yaml) (ablation);
- best: allowlisted, with rewritten descriptions (evals/datasets/rnd_a_best_descriptions.json).

Only the model's first tool call is scored; nothing is executed. Calls are cached in
data/processed/rnd_a/ by (tool set, task id), so a run stopped by rate limits resumes where it
left off. Delete that cache whenever the tasks, the prompt or a tool schema changes.
Run: `uv run python -m evals.runners.rnd_a_tool_granularity [--model openai/gpt-oss-20b]`.
"""

import argparse
import asyncio
import copy
import csv
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.shared.memory import create_connected_server_and_client_session
from openai import BadRequestError

from agent.config import load_config, load_prompt
from agent.llm import chat_model
from mcp_servers.marketplace.server import ServerSettings
from mcp_servers.marketplace.server import create_server as marketplace
from mcp_servers.portfolio.server import create_server as portfolio
from mcp_servers.portfolio.store import PortfolioSettings
from mcp_servers.workspace.server import WorkspaceSettings
from mcp_servers.workspace.server import create_server as workspace
from rag.index.embedder import FakeEmbedder

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "evals" / "datasets" / "rnd_a_tool_tasks.jsonl"
CACHE_DIR = ROOT / "data" / "processed" / "rnd_a"
RESULTS = ROOT / "evals" / "results"
TOOL_SETS = ("fine", "coarse", "allowlisted", "best")
BEST = ROOT / "evals" / "datasets" / "rnd_a_best_descriptions.json"
NODE_FOR_MODEL = "scout"  # the small model: tool calls are made by the cheap, frequent nodes
MAX_RETRIES = 10  # Groq's free tier allows 8,000 tokens a minute; the client waits on 429


async def server_tools() -> dict[str, list[dict[str, Any]]]:
    """Every MCP tool's name, description and input schema, grouped by server."""
    servers = {"marketplace": marketplace(ServerSettings(), lambda user: None),
               "portfolio": portfolio(PortfolioSettings(cache_dir=None), FakeEmbedder()),
               "workspace": workspace(WorkspaceSettings())}
    tools: dict[str, list[dict[str, Any]]] = {}
    for name, server in servers.items():
        async with create_connected_server_and_client_session(server) as session:
            tools[name] = [{"name": tool.name, "description": tool.description or "",
                            "parameters": tool.inputSchema}
                           for tool in (await session.list_tools()).tools]
    return tools


def as_function(tool: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": tool}


def coarse_tools(tools: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    coarse = []
    for server, server_tools in tools.items():
        actions = "\n".join(
            f"- {tool['name']}({', '.join(tool['parameters'].get('properties', {}))}): "
            f"{tool['description'].splitlines()[0]}" for tool in server_tools)
        coarse.append(as_function({
            "name": server, "description": f"The {server} server. Actions:\n{actions}",
            "parameters": {"type": "object", "required": ["action"], "properties": {
                "action": {"type": "string", "enum": [tool["name"] for tool in server_tools]},
                "arguments": {"type": "object", "description": "Arguments of the action"}}}}))
    return coarse


def tool_set(name: str, node: str, tools: dict[str, list[dict[str, Any]]]) -> list[dict]:
    fine = [tool for server_tools in tools.values() for tool in server_tools]
    if name == "coarse":
        return coarse_tools(tools)
    if name in ("allowlisted", "best"):
        allowed = load_config()["mcp"]["allowlists"][node]
        fine = [tool for tool in fine if tool["name"] in allowed]
    if name == "best":
        fine = [rewritten(tool) for tool in fine]
    return [as_function(tool) for tool in fine]


def rewritten(tool: dict[str, Any]) -> dict[str, Any]:
    """The tool with its description (and some argument descriptions) rewritten."""
    override = json.loads(BEST.read_text(encoding="utf-8"))["tools"].get(tool["name"])
    if not override:
        return tool
    tool = copy.deepcopy(tool) | {"description": override["description"]}
    for argument, text in override.get("arguments", {}).items():
        tool["parameters"]["properties"][argument]["description"] = text
    return tool


def first_call(set_name: str, tool_calls: list[dict[str, Any]]) -> tuple[str | None, dict]:
    if not tool_calls:
        return None, {}
    call = tool_calls[0]
    if set_name == "coarse":
        return call["args"].get("action"), call["args"].get("arguments") or {}
    return call["name"], call["args"]


def with_defaults(args: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    defaults = {key: prop["default"] for key, prop in schema.get("properties", {}).items()
                if "default" in prop}
    return defaults | args


def _same_instant(expected: str, actual: str) -> bool:
    try:
        return (datetime.fromisoformat(expected)
                == datetime.fromisoformat(actual))
    except ValueError:
        return False


def matches(expected: Any, actual: Any) -> bool:
    """`~text`: case-insensitive substring; lists: expected items present; else equal."""
    if isinstance(expected, str) and expected.startswith("~"):
        return expected[1:].lower() in str(actual).lower()
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(matches(value, actual.get(key))
                                                for key, value in expected.items())
    if isinstance(expected, list):
        found = [str(item).lower() for item in actual] if isinstance(actual, list) else []
        return all(str(item).lower() in found for item in expected)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, int | float):
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
    if isinstance(expected, str) and isinstance(actual, str):
        if expected[:4].isdigit() and "T" in expected:  # timestamps: compare the instant
            return _same_instant(expected, actual)
        return expected.strip().lower() == actual.strip().lower()
    return expected == actual


async def ask(model: Any, set_name: str, task: dict, tools: dict) -> dict[str, Any]:
    prompt = load_prompt("rnd_a_tool_use").format(node=task["node"],
                                                  instruction=task["instruction"])
    started = time.perf_counter()
    try:
        reply = await model.bind_tools(tool_set(set_name, task["node"], tools)).ainvoke(prompt)
    except BadRequestError as error:
        # The provider rejects a call to a tool that was not offered (e.g. 'workspace.run'):
        # a selection failure. Its token use is not reported, so it is left out of token means.
        if "tool call validation failed" not in str(error):
            raise
        return {"tool_calls": [], "invalid_call": str(error)[-160:], "input_tokens": None,
                "output_tokens": None, "seconds": round(time.perf_counter() - started, 2)}
    usage = reply.usage_metadata or {}
    return {"tool_calls": [{"name": call["name"], "args": call["args"]}
                           for call in reply.tool_calls],
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "seconds": round(time.perf_counter() - started, 2)}


def score(set_name: str, task: dict, raw: dict, schemas: dict[str, dict]) -> dict[str, Any]:
    tool, args = first_call(set_name, raw["tool_calls"])
    tool_ok = tool == task["expected_tool"]
    args_ok = tool_ok and all(
        matches(value, with_defaults(args, schemas[tool]).get(key))
        for key, value in task["expected_args"].items())
    return {"tool_set": set_name, "task_id": task["task_id"], "node": task["node"],
            "expected_tool": task["expected_tool"], "chosen_tool": tool, "tool_ok": tool_ok,
            "args_ok": args_ok, "invalid_call": "invalid_call" in raw,
            "tokens": None if raw["input_tokens"] is None
            else raw["input_tokens"] + raw["output_tokens"],
            "input_tokens": raw["input_tokens"], "seconds": raw["seconds"]}


def summarise(rows: list[dict]) -> dict[str, Any]:
    picked = [row for row in rows if row["tool_ok"]]
    return {"tasks": len(rows),
            "tool_selection_accuracy": round(len(picked) / len(rows), 3),
            "argument_accuracy_given_right_tool": round(
                sum(row["args_ok"] for row in picked) / len(picked), 3) if picked else None,
            "end_to_end_accuracy": round(sum(row["args_ok"] for row in rows) / len(rows), 3),
            "invalid_tool_calls": sum(row["invalid_call"] for row in rows),
            # over tasks whose token use the provider reported (not the invalid calls)
            "mean_tokens_per_task": round(statistics.mean(
                row["tokens"] for row in rows if row["tokens"] is not None)),
            "mean_input_tokens_per_task": round(statistics.mean(
                row["input_tokens"] for row in rows if row["input_tokens"] is not None))}


def load_cache(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {(row["tool_set"], row["task_id"]): row for row in rows}


async def run(model_name: str | None) -> dict[str, Any]:
    tasks = [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines()]
    tools = await server_tools()
    schemas = {tool["name"]: tool["parameters"] for group in tools.values() for tool in group}
    overrides: dict[str, Any] = {"max_retries": MAX_RETRIES}
    if model_name:
        overrides["model"] = model_name
    model = chat_model(NODE_FOR_MODEL, **overrides)
    cache_path = CACHE_DIR / f"{model.model_name.replace('/', '_')}.jsonl"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cached = load_cache(cache_path)
    rows = []
    for set_name in TOOL_SETS:
        for task in tasks:
            key = (set_name, task["task_id"])
            if key not in cached:
                cached[key] = {"tool_set": set_name, "task_id": task["task_id"],
                               **await ask(model, set_name, task, tools)}
                with cache_path.open("a", encoding="utf-8") as cache:
                    cache.write(json.dumps(cached[key]) + "\n")
            rows.append(score(set_name, task, cached[key], schemas))
    return {"model": model.model_name, "tasks_file": "evals/datasets/rnd_a_tool_tasks.jsonl",
            "tool_sets": {name: summarise([row for row in rows if row["tool_set"] == name])
                          for name in TOOL_SETS},
            "rows": rows}


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="override the small model of the active profile")
    result = asyncio.run(run(parser.parse_args().model))
    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = f"rnd_a_tool_granularity_{result['model'].replace('/', '_')}"
    with (RESULTS / f"{stem}.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(result["rows"][0]))
        writer.writeheader()
        writer.writerows(result["rows"])
    summary = {key: value for key, value in result.items() if key != "rows"}
    (RESULTS / f"{stem}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

"""Minimal read-only MCP stdio server."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from opensense.core.agent_workflow import summarize_agent_status
from opensense.core.issue_ref import parse_issue_reference
from opensense.core.patch import patch_dry_run
from opensense.models import Issue
from opensense.storage.packs import load_pack_payload as load_stored_pack_payload
from opensense.storage.packs import pack_paths, validate_pack_payload
from opensense.storage.watchlist import load_watchlist_data


TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "get_watchlist",
        "description": "Read OpenSense watched repositories and skills from the local workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "read_pack",
        "description": "Read pack.json and manifest.json for an existing OpenSense context pack.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_ref": {"type": "string"},
                "workspace": {"type": "string"},
            },
            "required": ["issue_ref"],
            "additionalProperties": False,
        },
    },
    {
        "name": "patch_dry_run",
        "description": "Evaluate patch suitability from an existing pack.json without modifying source files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_ref": {"type": "string"},
                "workspace": {"type": "string"},
            },
            "required": ["issue_ref"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_attempt_status",
        "description": "Read local OpenSense attempt status for one issue without modifying files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_ref": {"type": "string"},
                "workspace": {"type": "string"},
            },
            "required": ["issue_ref"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_pr_draft",
        "description": "Read a local pr-draft.md artifact for one issue attempt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_ref": {"type": "string"},
                "workspace": {"type": "string"},
            },
            "required": ["issue_ref"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_agent_handoff",
        "description": "Read a local agent-handoff.md artifact for one issue attempt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_ref": {"type": "string"},
                "workspace": {"type": "string"},
            },
            "required": ["issue_ref"],
            "additionalProperties": False,
        },
    },
)


def workspace_arg(arguments: dict[str, Any]) -> Path | None:
    value = arguments.get("workspace")
    if not value:
        return None
    root = Path(os.environ.get("OPENSENSE_MCP_WORKSPACE_ROOT", Path.cwd())).resolve()
    requested = Path(str(value)).resolve()
    try:
        requested.relative_to(root)
    except ValueError as exc:
        raise ValueError("Workspace must be inside the MCP server launch directory.") from exc
    return requested


def text_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]}


def load_pack_payload(issue_ref_text: str, workspace: Path | None = None) -> dict[str, Any]:
    issue_ref = parse_issue_reference(issue_ref_text)
    paths = pack_paths(issue_ref, workspace)
    if not paths.pack_json.exists() or not paths.manifest_json.exists():
        raise FileNotFoundError("Context pack not found. Run `opensense pack <issue-url>` first.")
    payload = load_stored_pack_payload(paths)
    validate_pack_payload(payload, issue_ref.ref)
    return payload


def issue_from_pack(pack: dict[str, Any]) -> Issue:
    issue = pack.get("issue", {})
    ref = parse_issue_reference(str(issue["ref"]))
    return Issue(
        owner=ref.owner,
        repo=ref.repo,
        number=ref.number,
        title=str(issue.get("title") or ""),
        labels=tuple(str(item) for item in issue.get("labels", [])),
        assignees=tuple(str(item) for item in issue.get("assignees", [])),
        comments=int(issue.get("comments") or 0),
        html_url=str(issue.get("url") or ref.url),
        repository_stars=int(issue.get("repository_stars") or 0),
        state=str(issue.get("state") or "open"),
    )


def require_artifact_metadata(path: Path, *, kind: str, issue_ref: str, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} metadata not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("kind") != kind or data.get("issue_ref") != issue_ref:
        raise ValueError(f"{label} metadata does not match the requested issue.")


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    workspace = workspace_arg(arguments)
    if name == "get_watchlist":
        watchlist = load_watchlist_data(workspace)
        return text_result({"repositories": list(watchlist.repositories), "skills": list(watchlist.skills)})
    if name == "read_pack":
        return text_result(load_pack_payload(str(arguments["issue_ref"]), workspace))
    if name == "patch_dry_run":
        payload = load_pack_payload(str(arguments["issue_ref"]), workspace)
        result = patch_dry_run(issue_from_pack(payload["pack"]))
        return text_result(asdict(result))
    if name == "get_attempt_status":
        issue_ref = parse_issue_reference(str(arguments["issue_ref"]))
        return text_result(summarize_agent_status(issue_ref, workspace).to_dict())
    if name == "read_pr_draft":
        issue_ref = parse_issue_reference(str(arguments["issue_ref"]))
        paths = pack_paths(issue_ref, workspace)
        load_pack_payload(issue_ref.ref, workspace)
        require_artifact_metadata(paths.pr_draft_json, kind="opensense.pr_draft", issue_ref=issue_ref.ref, label="PR draft")
        if not paths.pr_draft_md.exists():
            raise FileNotFoundError("PR draft not found. Run `opensense pr draft <issue-url>` first.")
        return text_result({"issue_ref": issue_ref.ref, "path": str(paths.pr_draft_md), "markdown": paths.pr_draft_md.read_text(encoding="utf-8")})
    if name == "read_agent_handoff":
        issue_ref = parse_issue_reference(str(arguments["issue_ref"]))
        paths = pack_paths(issue_ref, workspace)
        load_pack_payload(issue_ref.ref, workspace)
        require_artifact_metadata(paths.agent_handoff_json, kind="opensense.agent_handoff", issue_ref=issue_ref.ref, label="Agent handoff")
        if not paths.agent_handoff_md.exists():
            raise FileNotFoundError("Agent handoff not found. Run `opensense agent handoff <issue-url>` first.")
        return text_result({"issue_ref": issue_ref.ref, "path": str(paths.agent_handoff_md), "markdown": paths.agent_handoff_md.read_text(encoding="utf-8")})
    raise ValueError(f"Unknown tool: {name}")


def success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    if request_id is None:
        return None
    try:
        if method == "initialize":
            return success_response(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "opensense", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            )
        if method == "tools/list":
            return success_response(request_id, {"tools": list(TOOLS)})
        if method == "tools/call":
            params = request.get("params") or {}
            return success_response(request_id, call_tool(str(params.get("name")), dict(params.get("arguments") or {})))
        return error_response(request_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        return error_response(request_id, -32000, str(exc))


def serve(input_stream=sys.stdin, output_stream=sys.stdout) -> None:
    for line in input_stream:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = error_response(None, -32700, str(exc))
        else:
            response = handle_request(request)
        if response is not None:
            output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
            output_stream.flush()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()

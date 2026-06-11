import json
from pathlib import Path

from opensense.config import OpenSenseConfig, initialize_state
from opensense.core.issue_ref import parse_issue_reference
from opensense.mcp.server import handle_request
from opensense.storage.packs import pack_paths


def call(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    response = handle_request(request)
    assert response is not None
    return response


def tool_call(name: str, arguments: dict, request_id: int = 1) -> dict:
    return call("tools/call", {"name": name, "arguments": arguments}, request_id=request_id)


def text_payload(response: dict) -> dict:
    text = response["result"]["content"][0]["text"]
    return json.loads(text)


def write_sample_pack(workspace: Path) -> None:
    issue_ref = parse_issue_reference("owner/repo#7")
    paths = pack_paths(issue_ref, workspace)
    paths.root.mkdir(parents=True, exist_ok=True)
    pack = {
        "schema_version": 1,
        "issue": {
            "ref": "owner/repo#7",
            "url": "https://github.com/owner/repo/issues/7",
            "title": "Fix agent retrieval bug",
            "state": "open",
            "labels": ["bug", "agent"],
            "assignees": [],
            "comments": 2,
            "repository_stars": 1200,
        },
    }
    manifest = {
        "schema_version": 1,
        "kind": "opensense.pack_manifest",
        "issue_ref": "owner/repo#7",
        "secret_scan": {"status": "passed"},
        "safety": {"source_modified": False, "github_write_performed": False},
        "generated_files": ["pack.json", "manifest.json"],
    }
    paths.pack_json.write_text(json.dumps(pack), encoding="utf-8")
    paths.manifest_json.write_text(json.dumps(manifest), encoding="utf-8")


def test_mcp_initialize_and_tools_list() -> None:
    init_response = call("initialize", request_id=10)
    tools_response = call("tools/list", request_id=11)

    assert init_response["result"]["serverInfo"]["name"] == "opensense"
    tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
    assert tool_names == {"get_watchlist", "read_pack", "patch_dry_run"}


def test_mcp_get_watchlist_reads_local_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENSENSE_MCP_WORKSPACE_ROOT", str(tmp_path))
    initialize_state(tmp_path, OpenSenseConfig())

    response = tool_call("get_watchlist", {"workspace": str(tmp_path)})

    payload = text_payload(response)
    assert "vllm-project/vllm" in payload["repositories"]
    assert payload["skills"] == ["agent", "rag"]


def test_mcp_read_pack_returns_pack_and_manifest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENSENSE_MCP_WORKSPACE_ROOT", str(tmp_path))
    write_sample_pack(tmp_path)

    response = tool_call("read_pack", {"workspace": str(tmp_path), "issue_ref": "owner/repo#7"})

    payload = text_payload(response)
    assert payload["pack"]["issue"]["ref"] == "owner/repo#7"
    assert payload["manifest"]["kind"] == "opensense.pack_manifest"


def test_mcp_patch_dry_run_uses_existing_pack(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENSENSE_MCP_WORKSPACE_ROOT", str(tmp_path))
    write_sample_pack(tmp_path)

    response = tool_call("patch_dry_run", {"workspace": str(tmp_path), "issue_ref": "owner/repo#7"})

    payload = text_payload(response)
    assert payload["feasible"] is True
    assert payload["confidence"] == "medium"
    assert "Generate or refresh the context pack." in payload["suggested_steps"]


def test_mcp_missing_pack_returns_json_rpc_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENSENSE_MCP_WORKSPACE_ROOT", str(tmp_path))
    response = tool_call("read_pack", {"workspace": str(tmp_path), "issue_ref": "owner/repo#404"})

    assert response["error"]["code"] == -32000
    assert "Context pack not found" in response["error"]["message"]


def test_mcp_rejects_workspace_outside_launch_directory(tmp_path: Path) -> None:
    # OPENSENSE_MCP_WORKSPACE_ROOT is intentionally unset here, so cwd is the allowed root.
    outside = Path.cwd().resolve().parent

    response = tool_call("get_watchlist", {"workspace": str(outside)})

    assert response["error"]["code"] == -32000
    assert "Workspace must be inside" in response["error"]["message"]


def test_mcp_rejects_pack_with_failed_secret_scan(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENSENSE_MCP_WORKSPACE_ROOT", str(tmp_path))
    write_sample_pack(tmp_path)
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)
    manifest = json.loads(paths.manifest_json.read_text(encoding="utf-8"))
    manifest["secret_scan"]["status"] = "blocked"
    paths.manifest_json.write_text(json.dumps(manifest), encoding="utf-8")

    response = tool_call("read_pack", {"workspace": str(tmp_path), "issue_ref": "owner/repo#7"})

    assert response["error"]["code"] == -32000
    assert "secret scan has not passed" in response["error"]["message"]


def test_mcp_rejects_pack_issue_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENSENSE_MCP_WORKSPACE_ROOT", str(tmp_path))
    write_sample_pack(tmp_path)
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)
    manifest = json.loads(paths.manifest_json.read_text(encoding="utf-8"))
    manifest["issue_ref"] = "owner/repo#8"
    paths.manifest_json.write_text(json.dumps(manifest), encoding="utf-8")

    response = tool_call("read_pack", {"workspace": str(tmp_path), "issue_ref": "owner/repo#7"})

    assert response["error"]["code"] == -32000
    assert "does not match" in response["error"]["message"]

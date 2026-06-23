import json

from app.runtime.agent_runtime import _compact_tool_result_for_model


def test_compacts_large_http_body_before_sending_back_to_model():
    result = {
        "status_code": 200,
        "headers": {"content-type": "text/html"},
        "body": "x" * 50_000,
        "body_truncated": False,
        "duration_ms": 123,
        "request": {"method": "GET", "url": "https://example.com"},
    }

    compacted = _compact_tool_result_for_model(result)

    assert compacted["status_code"] == 200
    assert compacted["headers"] == {"content-type": "text/html"}
    assert compacted["request"] == {"method": "GET", "url": "https://example.com"}
    assert compacted["body"] == "x" * 8_000
    assert compacted["body_truncated_for_model"] is True
    assert compacted["original_body_chars"] == 50_000
    assert len(json.dumps(compacted, ensure_ascii=False)) < 12_000


def test_small_result_passes_through_unchanged():
    result = {"path": "/file.txt", "content": "hello world", "truncated": False, "size_bytes": 11}
    compacted = _compact_tool_result_for_model(result)
    assert compacted == result


def test_compacts_large_filesystem_read_content():
    result = {
        "path": "/workspace/bigfile.py",
        "content": "a" * 50_000,
        "truncated": False,
        "size_bytes": 50_000,
    }

    compacted = _compact_tool_result_for_model(result)

    assert compacted["path"] == "/workspace/bigfile.py"
    assert compacted["content"] == "a" * 8_000
    assert compacted["content_truncated_for_model"] is True
    assert compacted["original_content_chars"] == 50_000
    assert "hint" in compacted
    assert "offset" in compacted["hint"]
    assert len(json.dumps(compacted, ensure_ascii=False)) < 12_000


def test_compacts_large_filesystem_grep_results():
    results_list = [
        {"path": f"/file{i}.py", "line": i, "text": "match" * 10}
        for i in range(300)
    ]
    result = {
        "path": "/workspace",
        "pattern": "match",
        "count": 300,
        "truncated": True,
        "results": results_list,
    }

    compacted = _compact_tool_result_for_model(result)

    assert compacted["results_truncated_for_model"] is True
    assert len(compacted["results"]) <= 50
    assert compacted["total_results"] == 300
    assert len(json.dumps(compacted, ensure_ascii=False)) < 12_000


def test_generic_fallback_returns_scalar_fields_not_raw_json_string():
    """When no specific handler matches, scalar fields are preserved — not a raw truncated string."""
    result = {
        "status": "ok",
        "count": 42,
        "items": ["x" * 1000 for _ in range(500)],
    }

    compacted = _compact_tool_result_for_model(result)

    assert compacted["truncated_for_model"] is True
    assert compacted["status"] == "ok"
    assert compacted["count"] == 42
    assert "items" not in compacted or isinstance(compacted.get("items"), list)
    # Must be valid JSON and within size limit
    encoded = json.dumps(compacted, ensure_ascii=False)
    assert len(encoded) < 12_000

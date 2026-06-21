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

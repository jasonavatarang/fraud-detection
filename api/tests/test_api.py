from decimal import Decimal

from fastapi.testclient import TestClient

import api.main as api_module


client = TestClient(api_module.app)


def test_health_endpoint_is_database_independent():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "fraud-risk-api"}


def test_limit_validation_rejects_unbounded_raw_event_queries():
    response = client.get("/raw-events?limit=10000")

    assert response.status_code == 422


def test_top_users_uses_parameterized_limit(monkeypatch):
    captured = {}

    def fake_query(cache_key, sql, params=None, ttl=10):
        captured["cache_key"] = cache_key
        captured["sql"] = sql
        captured["params"] = params
        captured["ttl"] = ttl
        return []

    monkeypatch.setattr(api_module, "get_cached_or_query", fake_query)

    response = client.get("/stats/top-users?limit=25")

    assert response.status_code == 200
    assert response.json() == []
    assert captured["cache_key"] == "top_users_25"
    assert "LIMIT :limit" in captured["sql"]
    assert captured["params"] == {"limit": 25}


def test_make_json_safe_converts_nested_decimals():
    payload = {"score": Decimal("12.5"), "rows": [{"amount": Decimal("3.25")}]}

    assert api_module.make_json_safe(payload) == {
        "score": 12.5,
        "rows": [{"amount": 3.25}],
    }

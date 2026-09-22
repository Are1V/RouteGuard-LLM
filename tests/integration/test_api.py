from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.service import RouteGuardService

ROOT = Path(__file__).resolve().parents[2]


def client() -> TestClient:
    return TestClient(create_app(ROOT))


def test_health_models_and_configurations() -> None:
    api = client()
    assert api.get("/api/v1/health").json()["status"] == "ok"
    assert api.get("/api/v1/ready").json() == {
        "status": "ok",
        "version": "0.1.0",
        "simulated": True,
    }
    configurations = api.get("/api/v1/configurations").json()
    assert any(item["id"] == "demo" and item["simulated"] for item in configurations)
    models = api.get("/api/v1/models", params={"config": "demo"}).json()
    assert [model["name"] for model in models] == ["small", "medium", "large"]
    assert "options" not in models[0]


def test_local_frontend_origins_are_allowed() -> None:
    api = client()
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = api.options(
            "/api/v1/inference",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_inference_returns_real_trace_and_preserves_score_semantics() -> None:
    api = client()
    response = api.post(
        "/api/v1/inference",
        json={
            "query": "What is 17 multiplied by 23?",
            "answer_type": "numeric",
            "routing": "manual",
            "model": "medium",
            "verification": False,
            "escalation": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["simulated"] is True
    assert body["selected_model"] == "medium"
    assert body["routing_strategy"] == "fixed"
    assert body["attempts"][0]["confidence"]["calibrated"] is None
    assert body["attempts"][0]["confidence"]["calibrated_label"] == "unavailable"
    assert body["attempts"][0]["verification"] is None
    assert body["totals"]["cost_usd"] is None
    assert body["final_answer"] is not None
    assert "unknown" not in body["attempts"][0]["raw_text"]
    trace = api.get(f"/api/v1/traces/{body['trace_id']}")
    assert trace.status_code == 200
    assert trace.json()["routing"]["model"] == "medium"


def test_api_rejects_unknown_resources_and_path_traversal() -> None:
    api = client()
    assert api.get("/api/v1/models", params={"config": "../../secret"}).status_code == 404
    assert api.get("/api/v1/experiments/not-a-run/metrics").status_code == 404
    invalid = api.post(
        "/api/v1/inference",
        json={"query": "hello", "routing": "manual", "model": "missing"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_request"


def test_explicit_language_override_is_distinct_from_detection() -> None:
    api = client()
    response = api.post(
        "/api/v1/inference",
        json={
            "query": "What is the capital of Kazakhstan?",
            "language": "kk",
            "escalation": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["detected_language"] == "kk"
    assert response.json()["language_source"] == "requested"


def test_public_api_never_executes_generated_code() -> None:
    api = client()
    response = api.post(
        "/api/v1/inference",
        json={
            "query": "Write a function.",
            "answer_type": "code",
            "routing": "manual",
            "model": "small",
            "escalation": False,
        },
    )
    assert response.status_code == 200
    verification = response.json()["attempts"][0]["verification"]
    assert verification is not None
    assert verification["verifier"] != "code_execution"


def test_experiment_metrics_are_strict_json() -> None:
    api = client()
    runs = api.get("/api/v1/experiments").json()["experiments"]
    main = next((run for run in runs if run["id"].startswith("main_")), None)
    if main is None:
        return
    response = api.get(f"/api/v1/experiments/{main['id']}/metrics")
    assert response.status_code == 200
    assert response.json()["systems"]["routeguard"]["metrics"]["accuracy"]["mean"] > 0


def test_published_metrics_are_available_without_raw_run(
    tmp_path: Path,
) -> None:
    published = tmp_path / "docs" / "results" / "main"
    published.mkdir(parents=True)
    (published / "PROVENANCE.json").write_text(
        '{"run_id":"main_nogit","seeds":[0],"simulated":false,"data":{"n_items":2}}',
        encoding="utf-8",
    )
    (published / "metrics.json").write_text(
        '{"simulated":false,"systems":{"routeguard":{"metrics":{}}}}',
        encoding="utf-8",
    )
    service = RouteGuardService(tmp_path)
    experiments = service.experiments()
    assert [item.id for item in experiments] == ["main_nogit"]
    assert experiments[0].name == "main"
    assert experiments[0].has_metrics is True
    assert service.metrics("main_nogit")["simulated"] is False


def test_published_summary_accepts_null_optional_metadata(tmp_path: Path) -> None:
    published = tmp_path / "docs" / "results" / "tool_use"
    published.mkdir(parents=True)
    (published / "PROVENANCE.json").write_text(
        '{"run_id":"tool_use_nogit","seeds":null,"data":null,"simulated":false}',
        encoding="utf-8",
    )

    service = RouteGuardService(tmp_path)
    experiments = service.experiments()

    assert len(experiments) == 1
    assert experiments[0].id == "tool_use_nogit"
    assert experiments[0].seeds == []
    assert experiments[0].item_count is None
    assert experiments[0].has_metrics is False


def test_examples_are_served_only_for_the_simulated_demo() -> None:
    api = client()
    examples = api.get("/api/v1/examples", params={"config": "demo"}).json()
    assert examples, "the bundled demo fixture should provide example queries"
    assert {"query", "answer_type", "language", "category"} == set(examples[0])
    # A real-model configuration accepts any query, so it advertises no fixed list.
    assert api.get("/api/v1/examples", params={"config": "local_hf"}).json() == []
    assert api.get("/api/v1/examples", params={"config": "nope"}).status_code == 404


def test_examples_are_answerable_by_the_simulated_backend() -> None:
    api = client()
    example = api.get("/api/v1/examples", params={"config": "demo"}).json()[0]
    response = api.post(
        "/api/v1/inference",
        json={"query": example["query"], "answer_type": example["answer_type"]},
    )
    assert response.status_code == 200
    assert response.json()["final_answer"] not in (None, "unknown")


def _unreachable_config(root: Path) -> None:
    """Write a config whose model server is guaranteed not to answer."""
    configs = root / "configs"
    configs.mkdir(parents=True, exist_ok=True)
    (configs / "offline.yaml").write_text(
        "name: offline\n"
        "models:\n"
        "  - name: remote\n"
        "    backend: openai_compatible\n"
        "    model_id: m\n"
        "    params_b: 1.0\n"
        "    options: {base_url: 'http://127.0.0.1:9', max_retries: 0, timeout_s: 1}\n"
        "confidence: {calibration: none}\n"
        "escalation: {enabled: false}\n"
        "cache: {enabled: false}\n",
        encoding="utf-8",
    )


def test_unreachable_model_backend_reports_503_not_500(tmp_path: Path) -> None:
    _unreachable_config(tmp_path)
    api = TestClient(create_app(tmp_path))
    response = api.post("/api/v1/inference", json={"query": "hello", "config": "offline"})
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "backend_unavailable"
    # The operator needs to see which endpoint failed.
    assert "127.0.0.1:9" in body["error"]["message"]


def test_missing_api_key_reports_503_and_never_leaks_the_variable_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ROUTEGUARD_TEST_KEY", raising=False)
    configs = tmp_path / "configs"
    configs.mkdir(parents=True)
    (configs / "hosted.yaml").write_text(
        "name: hosted\n"
        "models:\n"
        "  - name: remote\n"
        "    backend: openai_compatible\n"
        "    model_id: m\n"
        "    params_b: 1.0\n"
        "    options: {base_url: 'https://example.invalid/v1',"
        " api_key_env: ROUTEGUARD_TEST_KEY}\n"
        "confidence: {calibration: none}\n"
        "escalation: {enabled: false}\n"
        "cache: {enabled: false}\n",
        encoding="utf-8",
    )
    api = TestClient(create_app(tmp_path))
    response = api.post("/api/v1/inference", json={"query": "hello", "config": "hosted"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "backend_unavailable"
    assert "ROUTEGUARD_TEST_KEY is not set" in response.json()["error"]["message"]


def test_unexpected_errors_keep_the_documented_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = TestClient(create_app(ROOT), raise_server_exceptions=False)
    monkeypatch.setattr(
        "apps.api.service.RouteGuardService.experiments",
        lambda self: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    response = api.get("/api/v1/experiments")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    # The client gets a reference, not the internal failure text.
    assert "boom" not in response.text
    assert body["error"]["details"]["incident"]


def test_blocked_origin_is_logged_for_the_operator(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A browser discards the response silently, so the server has to say something."""
    monkeypatch.setenv("ROUTEGUARD_CORS_ORIGINS", "http://localhost:3000")
    api = TestClient(create_app(ROOT))
    with caplog.at_level("WARNING", logger="routeguard.api"):
        allowed = api.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert not caplog.records

        blocked = api.get("/api/v1/health", headers={"Origin": "http://localhost:3999"})
        assert "access-control-allow-origin" not in blocked.headers
    assert any("http://localhost:3999" in record.getMessage() for record in caplog.records)

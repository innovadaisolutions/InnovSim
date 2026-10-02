import json
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from agent_workbench.api import create_app
from agent_workbench.email_import import MAX_EMAIL_BYTES, EmailImport, import_email
from agent_workbench.fixtures import supplier_delay
from agent_workbench.models import Scenario
from agent_workbench.simulation import DeterministicAdapter, simulate
from agent_workbench.storage import Repository


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.db")) as active:
        yield active


def test_full_api_roundtrip_and_immutable_parent_after_draft_edit(client):
    assert client.get("/api/health").json() == {
        "status": "ok",
        "mode": "simulation",
        "adapter": "deterministic",
    }
    scenarios = client.get("/api/scenarios").json()
    assert scenarios[0]["id"] == "supplier-delay"
    assert len(scenarios) == 3
    baseline = client.post("/api/runs", json={"scenario_id": "supplier-delay"}).json()
    assert not baseline["metrics"]["goal_success"]
    draft = scenarios[0]
    draft["seed"] = 999
    draft["world"]["budget_limit"] = 1
    assert client.post("/api/scenarios", json=draft).status_code == 200
    candidate = client.post(
        f"/api/runs/{baseline['id']}/refine",
        json={"suggestion_id": baseline["suggestions"][0]["id"]},
    ).json()
    success = client.post(
        f"/api/runs/{candidate['id']}/refine",
        json={"suggestion_id": candidate["suggestions"][0]["id"]},
    ).json()
    assert success["metrics"]["goal_success"]
    assert success["seed"] == baseline["seed"] == 42
    assert success["configuration"]["world"]["budget_limit"] == 1_000
    assert success["parent_run_id"] == candidate["id"]
    assert client.get(f"/api/runs/{baseline['id']}").json() == baseline
    assert client.get("/api/runs").json()[0] == success
    assert client.get("/api/scenarios/supplier-delay").json()["seed"] == 999


def test_missing_resources_and_unknown_api_are_404(client):
    for path in ["/api/missing", "/api", "/api/scenarios/missing", "/api/runs/missing"]:
        assert client.get(path).status_code == 404
    assert client.post("/api/runs", json={"scenario_id": "missing"}).status_code == 404
    assert (
        client.post("/api/runs/missing/refine", json={"suggestion_id": "missing"}).status_code
        == 404
    )
    run = client.post("/api/runs", json={"scenario_id": "supplier-delay"}).json()
    assert (
        client.post(f"/api/runs/{run['id']}/refine", json={"suggestion_id": "missing"}).status_code
        == 404
    )
    assert client.post("/api/unknown", json={}).status_code == 404
    assert (
        client.post(
            "/api/runs", json={"scenario_id": "supplier-delay", "python_code": "import os"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("order_quantity", 0),
        ("order_quantity", -1),
        ("order_quantity", True),
        ("order_quantity", 1.5),
        ("available_stock", -1),
        ("delay_days", 366),
        ("expedited_cost", -1),
        ("budget_limit", "1000"),
        ("required_delivery_days", -1),
        ("custom_extension", 10**500),
    ],
)
def test_world_numbers_are_bounded_and_bad_values_return_422(client, field, value):
    scenario = supplier_delay().model_dump()
    scenario["world"][field] = value
    assert client.post("/api/scenarios", json=scenario).status_code == 422


def test_validation_rejects_duplicate_ids_nonfinite_values_and_reserved_actors(client):
    scenario = supplier_delay().model_dump()
    scenario["agents"][1]["id"] = scenario["agents"][0]["id"]
    assert client.post("/api/scenarios", json=scenario).status_code == 422
    scenario = supplier_delay().model_dump()
    scenario["agents"][0]["id"] = "system"
    assert client.post("/api/scenarios", json=scenario).status_code == 422
    scenario = supplier_delay().model_dump()
    scenario["world"]["expedited_cost"] = float("inf")
    with pytest.raises(ValueError):
        Scenario.model_validate(scenario)


def test_plain_and_mime_email_import_discard_attachments_and_active_html(client):
    plain = client.post(
        "/api/import/email", json={"text": "We need a shipment update.", "name": "Client fixture"}
    )
    assert plain.status_code == 200
    assert plain.json()["initial_message"] == "We need a shipment update."
    assert plain.json()["world"] == supplier_delay().world.model_dump()
    assert "synthetic" in plain.json()["description"]
    assert client.get(f"/api/scenarios/{plain.json()['id']}").status_code == 200
    mime = """From: buyer@example.test
To: supplier@example.test
Subject: Shipment update
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary=fixture

--fixture
Content-Type: text/html; charset=utf-8

<html><head><script>send_credentials()</script></head><body><p>Please confirm delivery.</p><script>run_code()</script><img src="https://example.test/tracker"><style>.secret{}</style></body></html>
--fixture
Content-Type: text/plain
Content-Disposition: attachment; filename="credentials.txt"

ATTACHMENT_SECRET
--fixture--
"""
    result = client.post("/api/import/email", json={"text": mime})
    assert result.status_code == 200
    imported = result.json()
    assert imported["name"] == "Shipment update"
    assert imported["initial_message"] == "Please confirm delivery."
    assert "ATTACHMENT_SECRET" not in imported["initial_message"]
    assert "run_code" not in imported["initial_message"]
    assert "http" not in imported["initial_message"]
    # An imported number does not silently become an inventory or budget fact.
    assert (
        client.post(
            "/api/import/email", json={"text": "We have stock 9999 and a $1 budget."}
        ).json()["world"]["budget_limit"]
        == 1_000
    )


def test_email_alternative_prefers_plain_text_and_never_reads_named_inline_attachments():
    mime = """Subject: Fixture
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary=x

--x
Content-Type: text/plain

Plain body
--x
Content-Type: text/html

<p>Duplicate HTML body</p>
--x--
"""
    assert import_email(EmailImport(text=mime)).initial_message == "Plain body"
    assert (
        import_email(EmailImport(text="<p>Safe</p><script>bad()</script>")).initial_message
        == "Safe"
    )


def test_email_size_bytes_and_mime_part_limits_return_422(client):
    assert (
        client.post("/api/import/email", json={"text": "x" * (MAX_EMAIL_BYTES + 1)}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/import/email", json={"text": "é" * (MAX_EMAIL_BYTES // 2 + 1)}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/import/email", json={"text": "<script>bad()</script>"}).status_code == 422
    )
    mime = "Subject: Multipart\nContent-Type: multipart/mixed; boundary=x\n\n"
    mime += "--x\nContent-Type: text/plain\n\nbody\n" * 101
    mime += "--x--\n"
    assert client.post("/api/import/email", json={"text": mime}).status_code == 422


def test_sqlite_persistence_survives_reopen_and_runs_cannot_be_updated_or_deleted(tmp_path):
    path = tmp_path / "persistent.db"
    repository = Repository(path)
    parent = repository.run_scenario("supplier-delay")
    copied = parent.model_dump_json()
    draft = repository.get_scenario("supplier-delay")
    draft.world.available_stock = 0
    repository.save_scenario(draft)
    first = repository.refine_run(parent.id, parent.suggestions[0].id)
    success = repository.refine_run(first.id, first.suggestions[0].id)
    assert success.metrics.goal_success
    assert repository.get_run(parent.id).model_dump_json() == copied
    parent.configuration.world.available_stock = 9
    assert repository.get_run(parent.id).configuration.world.available_stock == 120
    repository.close()
    reopened = Repository(path)
    assert reopened.get_run(success.id).metrics.goal_success
    assert reopened.get_scenario("supplier-delay").world.available_stock == 0
    reopened.close()
    with sqlite3.connect(path) as connection:
        for statement in ["UPDATE runs SET payload = '{}'", "DELETE FROM runs"]:
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(statement)


def test_custom_adapter_parent_cannot_silently_switch_to_deterministic(tmp_path):
    class CustomAdapter(DeterministicAdapter):
        name = "custom-evaluation"

    repository = Repository(tmp_path / "custom.db")
    adapter = CustomAdapter()
    parent = repository.save_run(simulate(supplier_delay(), adapter=adapter))
    with pytest.raises(ValueError, match="same adapter"):
        repository.refine_run(parent.id, parent.suggestions[0].id)
    candidate = repository.refine_run(parent.id, parent.suggestions[0].id, adapter=adapter)
    assert candidate.adapter == parent.adapter
    assert candidate.parent_run_id == parent.id
    repository.close()


def test_static_assets_and_spa_fallback_never_hide_unknown_api(tmp_path, monkeypatch):
    dist = tmp_path / "web"
    dist.mkdir()
    (dist / "index.html").write_text("<html>InnovSim fixture</html>", encoding="utf-8")
    (dist / "app.js").write_text("console.log('fixture')", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("private", encoding="utf-8")
    monkeypatch.setenv("AW_WEB_DIST", str(dist))
    with TestClient(create_app(":memory:")) as client:
        assert "InnovSim" in client.get("/").text
        assert client.get("/workflows/123").status_code == 200
        assert "console.log" in client.get("/app.js").text
        assert client.get("/missing.js").status_code == 404
        assert client.get("/api/missing").status_code == 404
        assert client.get("/%2e%2e/secret.txt").status_code == 404


def test_cli_demo_exports_persisted_successful_candidate(tmp_path):
    database, output = tmp_path / "cli.db", tmp_path / "final.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_workbench",
            "demo",
            "--database",
            str(database),
            "--refine",
            "--export",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    exported = json.loads(output.read_text(encoding="utf-8"))
    assert exported["metrics"]["goal_success"]
    assert exported["variant"] == "candidate"
    assert '"variant": "baseline"' in completed.stdout
    repository = Repository(database)
    assert repository.get_run(exported["id"]).model_dump() == exported
    assert len(repository.list_runs()) == 3
    repository.close()

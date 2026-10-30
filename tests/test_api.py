from fastapi.testclient import TestClient

from app import main
from app.database import engine_for_url


def use_test_database(monkeypatch, tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(main, "DATABASE_URL", database_url)
    engine_for_url.cache_clear()


def test_lead_crud_and_opt_out_blocks_draft(tmp_path, monkeypatch):
    use_test_database(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "")
    with TestClient(main.app) as client:
        response = client.post("/api/leads", json={
            "name": "Taylor Reed",
            "company": "Example Co",
            "status": "proposal",
            "deal_value": 2500,
            "opted_out": True,
        })
        assert response.status_code == 201
        lead = response.json()
        assert lead["name"] == "Taylor Reed"
        assert lead["priority"]["score"] == 0

        blocked = client.post(
            f"/api/leads/{lead['id']}/draft",
            json={"channel": "email", "goal": "restart the conversation"},
        )
        assert blocked.status_code == 409

        updated = client.patch(f"/api/leads/{lead['id']}", json={"opted_out": False})
        assert updated.status_code == 200
        assert updated.json()["opted_out"] is False

        listing = client.get("/api/leads?q=Taylor")
        assert listing.status_code == 200
        assert len(listing.json()) == 1

        deleted = client.delete(f"/api/leads/{lead['id']}")
        assert deleted.status_code == 204
        assert client.get(f"/api/leads/{lead['id']}").status_code == 404


def test_health_does_not_expose_api_key(tmp_path, monkeypatch):
    use_test_database(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "never-return-this-secret")
    with TestClient(main.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["gemini_configured"] is True
        assert "never-return-this-secret" not in response.text


def test_knowledge_requires_api_key(tmp_path, monkeypatch):
    use_test_database(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "")
    with TestClient(main.app) as client:
        response = client.post("/api/knowledge", json={
            "title": "Product facts",
            "content": "Lead Reviver helps sales teams prioritize follow-up.",
        })
        assert response.status_code == 503


def test_invalid_lead_payload_is_rejected(tmp_path, monkeypatch):
    use_test_database(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        response = client.post("/api/leads", json={"name": "", "deal_value": -1})
        assert response.status_code == 422

from fastapi.testclient import TestClient

from app.main import create_app


def _dist(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Vellum</title>")
    return dist


def test_serves_index_when_dist_present(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_WEB_DIST", str(_dist(tmp_path)))
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "Vellum" in r.text


def test_api_route_takes_precedence_over_static(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_WEB_DIST", str(_dist(tmp_path)))
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_starts_without_dist(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_WEB_DIST", str(tmp_path / "missing"))
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 404

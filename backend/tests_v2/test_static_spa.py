"""Phase 3: the optional SPA static mount (guarded, additive).

`TRADEQUEST2_STATIC_DIR` points the app at a built frontend.  These tests
verify the mount serves index.html and real files, falls back to index.html
for client-side routes, and never shadows the JSON API.
"""
from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def test_spa_served_when_build_present(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>tq-spa</html>", encoding="utf-8")
    (tmp_path / "favicon.ico").write_bytes(b"\x00\x01")
    monkeypatch.setenv("TRADEQUEST2_STATIC_DIR", str(tmp_path))
    try:
        import app2.main as main_module

        reloaded = importlib.reload(main_module)
        with TestClient(reloaded.app) as client:
            # SPA index at root
            r = client.get("/")
            assert r.status_code == 200
            assert "tq-spa" in r.text
            # real files served
            r = client.get("/favicon.ico")
            assert r.status_code == 200
            # client-side route falls back to index.html
            r = client.get("/quests")
            assert r.status_code == 200
            assert "tq-spa" in r.text
            # path traversal cannot escape the SPA dir
            r = client.get("/..%2f..%2fREADME.md")
            assert "tq-spa" in r.text
            # the API still wins over the catch-all
            r = client.get("/api/system/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"
    finally:
        monkeypatch.delenv("TRADEQUEST2_STATIC_DIR", raising=False)
        import app2.main as main_module

        importlib.reload(main_module)  # restore unmounted app for later tests


def test_spa_absent_changes_nothing(tmp_path, monkeypatch):
    # Point the static dir at a path that does not exist so the guard is
    # exercised whether or not frontend_v2/dist has been built locally: the
    # app must keep serving the JSON API only.
    monkeypatch.setenv("TRADEQUEST2_STATIC_DIR", str(tmp_path / "does-not-exist"))
    try:
        import app2.main as main_module

        reloaded = importlib.reload(main_module)
        with TestClient(reloaded.app) as client:
            assert client.get("/api/system/health").status_code == 200
            assert client.get("/").status_code == 404
    finally:
        monkeypatch.delenv("TRADEQUEST2_STATIC_DIR", raising=False)
        import app2.main as main_module

        importlib.reload(main_module)

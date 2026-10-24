import app as voting_app


FRONTEND_ORIGIN = "https://frontend.example.test"


def _allow_frontend(monkeypatch):
    monkeypatch.setitem(voting_app.app.config, "FRONTEND_ORIGINS", {FRONTEND_ORIGIN})


def test_api_session_allows_configured_frontend(client, system, monkeypatch):
    _allow_frontend(monkeypatch)
    response = client.get("/api/session", headers={"Origin": FRONTEND_ORIGIN})

    assert response.status_code == 200
    assert response.json["authenticated"] is False
    assert response.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


def test_api_preflight_rejects_unconfigured_frontend(client, system, monkeypatch):
    _allow_frontend(monkeypatch)
    response = client.options("/api/login", headers={
        "Origin": "https://malicious.example.test",
        "Access-Control-Request-Method": "POST",
    })

    assert response.status_code == 403
    assert "Access-Control-Allow-Origin" not in response.headers


def test_api_admin_mutation_requires_allowed_origin_and_admin(
    client, system, monkeypatch
):
    _allow_frontend(monkeypatch)
    response = client.post(
        "/api/admin/settings",
        json={"action": "open_voting"},
        headers={"Origin": FRONTEND_ORIGIN},
    )

    assert response.status_code == 403
    assert response.json["success"] is False
    assert response.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN

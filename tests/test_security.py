import app as voting_app
from controllers import auth as auth_controller
from database.mongo_db import MongoConnectionError


def test_session_cookie_configuration_is_http_only_and_same_site():
    assert voting_app.app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert voting_app.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert voting_app.app.config["SESSION_COOKIE_SECURE"] is voting_app.IS_PRODUCTION
    assert bool(voting_app.app.secret_key)


def test_login_success_message_does_not_reveal_email_or_otp(client, system):
    response = client.post("/login", data={"rollno": "A101", "password": "password-a"})
    body = response.get_data(as_text=True)

    assert "student.a@example.test" not in body
    assert system.sent_emails[0]["otp"] not in body


def test_mongodb_error_returns_generic_service_message(client, monkeypatch):
    def raise_database_error(*args, **kwargs):
        raise MongoConnectionError("internal connection detail")

    monkeypatch.setattr(auth_controller, "is_login_rate_limited", raise_database_error)

    response = client.post("/login", data={"rollno": "A101", "password": "password-a"})

    assert response.status_code == 503
    assert b"temporarily unavailable" in response.data
    assert b"internal connection detail" not in response.data


def test_logout_invalidates_pending_otp_session(client, system):
    client.post("/login", data={"rollno": "A101", "password": "password-a"})
    assert "A101" in system.otp_records

    response = client.get("/logout")
    with client.session_transaction() as session:
        assert "pending_rollno" not in session
        assert "rollno" not in session
        assert "admin" not in session

    assert response.status_code == 302
    assert client.post("/verify_otp", data={"otp": system.sent_emails[-1]["otp"]}).status_code == 200
import app as voting_app
from werkzeug.security import check_password_hash


def test_valid_password_step_sets_pending_not_authenticated_session(client, system):
    response = client.post("/login", data={"rollno": "A101", "password": "password-a"})

    assert response.status_code == 200
    assert b"verification code has been sent" in response.data
    with client.session_transaction() as session:
        assert session["pending_rollno"] == "A101"
        assert "rollno" not in session
    assert system.sent_emails[0]["recipient"] == "student.a@example.test"


def test_unknown_roll_number_is_rejected_without_sending_otp(client, system):
    response = client.post("/login", data={"rollno": "UNKNOWN", "password": "password-a"})

    assert b"Invalid credentials or account is not approved" in response.data
    assert system.sent_emails == []


def test_wrong_password_is_rejected(client, system):
    response = client.post("/login", data={"rollno": "A101", "password": "wrong"})

    assert b"Invalid credentials or account is not approved" in response.data
    assert system.sent_emails == []


def test_empty_credentials_are_rejected(client, system):
    response = client.post("/login", data={"rollno": "", "password": ""})

    assert response.status_code == 200
    assert b"Invalid credentials or account is not approved" in response.data
    assert system.sent_emails == []


def test_missing_roll_number_field_returns_bad_request(client):
    assert client.post("/login", data={"password": "password-a"}).status_code == 400


def test_json_send_otp_endpoint_uses_existing_student_email(client, system):
    response = client.post("/send_otp", json={"rollno": "B202", "password": "password-b"})

    assert response.status_code == 200
    assert response.json["success"] is True
    assert system.sent_emails[-1]["recipient"] == "student.b@example.test"
    assert "otp" not in response.json


def test_json_send_otp_rejects_invalid_credentials(client, system):
    response = client.post("/send_otp", json={"rollno": "B202", "password": "wrong"})

    assert response.status_code == 401
    assert response.json["success"] is False
    assert system.sent_emails == []


def test_login_input_is_trimmed(client, system):
    response = client.post("/login", data={"rollno": " A101 ", "password": "password-a"})

    assert response.status_code == 200
    assert system.sent_emails[0]["recipient"] == "student.a@example.test"


def test_unapproved_student_cannot_start_login(client, system):
    system.students["A101"]["approved"] = False

    response = client.post("/login", data={"rollno": "A101", "password": "password-a"})

    assert b"Invalid credentials or account is not approved" in response.data
    assert system.sent_emails == []


def test_login_rate_limit_blocks_attempt(client, system):
    system.login_attempts["A101"] = voting_app.MAX_LOGIN_ATTEMPTS

    response = client.post("/login", data={"rollno": "A101", "password": "password-a"})

    assert b"Too many attempts" in response.data
    assert system.sent_emails == []


def test_valid_admin_credentials_create_admin_session(client, monkeypatch):
    monkeypatch.setitem(voting_app.app.config, "ADMIN_ID", "admin-test")
    monkeypatch.setitem(voting_app.app.config, "ADMIN_PHONE", "5550100")
    monkeypatch.setitem(voting_app.app.config, "ADMIN_PASSWORD", "admin-test-password")

    response = client.post("/login", data={
        "rollno": "admin-test",
        "mobile": "5550100",
        "password": "admin-test-password",
    })

    assert response.status_code == 302
    assert response.location.endswith("/admin")
    with client.session_transaction() as session:
        assert session.get("admin") is True
        assert "rollno" not in session


def test_invalid_admin_credentials_do_not_create_admin_session(client, monkeypatch):
    monkeypatch.setitem(voting_app.app.config, "ADMIN_ID", "admin-test")
    monkeypatch.setitem(voting_app.app.config, "ADMIN_PHONE", "5550100")
    monkeypatch.setitem(voting_app.app.config, "ADMIN_PASSWORD", "admin-test-password")

    response = client.post("/login", data={
        "rollno": "admin-test",
        "mobile": "wrong-phone",
        "password": "wrong-password",
    })

    assert response.status_code == 200
    assert b"Invalid credentials" in response.data
    with client.session_transaction() as session:
        assert "admin" not in session


def test_password_hash_helper_uses_werkzeug_hashing():
    encoded = voting_app.hash_password("example-password")

    assert encoded != "example-password"
    assert check_password_hash(encoded, "example-password")
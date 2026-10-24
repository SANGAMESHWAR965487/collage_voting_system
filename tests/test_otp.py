from datetime import datetime, timedelta, timezone
import smtplib

import app as voting_app
from controllers import auth as auth_controller


def start_login(client, rollno="A101", password="password-a"):
    return client.post("/login", data={"rollno": rollno, "password": password})


def test_otp_is_six_digits_hashed_and_not_returned(client, system):
    response = start_login(client)
    sent_code = system.sent_emails[-1]["otp"]
    record = system.otp_records["A101"]

    assert response.status_code == 200
    assert len(sent_code) == 6 and sent_code.isdigit()
    assert record["otp_hash"] != sent_code
    with voting_app.app.app_context():
        assert record["otp_hash"] == auth_controller._otp_digest("A101", sent_code)
    assert sent_code not in response.get_data(as_text=True)
    assert record["expires_at"] - record["sent_at"] == timedelta(seconds=300)


def test_student_specific_email_is_used(client, system):
    start_login(client, "A101", "password-a")
    second_client = voting_app.app.test_client()
    start_login(second_client, "B202", "password-b")

    assert [email["recipient"] for email in system.sent_emails] == [
        "student.a@example.test",
        "student.b@example.test",
    ]


def test_correct_otp_creates_authenticated_session(client, system):
    start_login(client)

    response = client.post("/verify_otp", data={"otp": system.sent_emails[-1]["otp"]})

    assert response.status_code == 302
    assert response.location.endswith("/vote")
    with client.session_transaction() as session:
        assert session["rollno"] == "A101"
        assert "pending_rollno" not in session
    assert "A101" not in system.otp_records


def test_wrong_otp_is_rejected_and_counted(client, system):
    start_login(client)

    response = client.post("/verify_otp", data={"otp": "000000"})

    assert b"Invalid OTP" in response.data
    assert system.otp_records["A101"]["attempts"] == 1
    with client.session_transaction() as session:
        assert "rollno" not in session


def test_expired_otp_is_deleted(client, system):
    start_login(client)
    system.otp_records["A101"]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)

    response = client.post("/verify_otp", data={"otp": system.sent_emails[-1]["otp"]})

    assert b"OTP expired" in response.data
    assert "A101" not in system.otp_records


def test_otp_cannot_be_reused(client, system):
    start_login(client)
    code = system.sent_emails[-1]["otp"]
    assert client.post("/verify_otp", data={"otp": code}).status_code == 302

    response = client.post("/verify_otp", data={"otp": code})

    assert b"OTP expired" in response.data
    with client.session_transaction() as session:
        assert session.get("rollno") == "A101"


def test_five_failed_otp_attempts_invalidate_challenge(client, system):
    start_login(client)
    for _ in range(voting_app.MAX_LOGIN_ATTEMPTS):
        response = client.post("/verify_otp", data={"otp": "000000"})

    assert b"Too many incorrect OTP attempts" in response.data
    assert "A101" not in system.otp_records
    with client.session_transaction() as session:
        assert "rollno" not in session
        assert "pending_rollno" not in session


def test_resend_sends_new_code_and_invalidates_old_code(client, system):
    start_login(client)
    old_code = system.sent_emails[-1]["otp"]
    system.otp_records["A101"]["sent_at"] -= timedelta(seconds=voting_app.OTP_RESEND_COOLDOWN_SECONDS + 1)

    response = client.post("/resend_otp")
    new_code = system.sent_emails[-1]["otp"]

    assert response.status_code == 200
    assert new_code != old_code
    assert system.sent_emails[-1]["recipient"] == "student.a@example.test"
    assert b"Invalid OTP" in client.post("/verify_otp", data={"otp": old_code}).data
    assert client.post("/verify_otp", data={"otp": new_code}).status_code == 302


def test_resend_cooldown_returns_rate_limit(client, system):
    start_login(client)

    response = client.post("/resend_otp")

    assert response.status_code == 429
    assert b"Please wait" in response.data
    assert len(system.sent_emails) == 1


def test_resend_limit_is_enforced(client, system):
    start_login(client)
    system.otp_records["A101"]["resend_count"] = voting_app.MAX_OTP_RESENDS
    system.otp_records["A101"]["sent_at"] -= timedelta(seconds=voting_app.OTP_RESEND_COOLDOWN_SECONDS + 1)

    response = client.post("/resend_otp")

    assert response.status_code == 429
    assert b"resend limit" in response.data.lower()
    assert len(system.sent_emails) == 1


def test_resend_expired_challenge_requires_new_login(client, system):
    start_login(client)
    system.otp_records["A101"]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)

    response = client.post("/resend_otp")

    assert b"verification request expired" in response.data.lower()
    assert "A101" not in system.otp_records
    with client.session_transaction() as session:
        assert "pending_rollno" not in session


def test_smtp_failure_clears_otp_and_pending_session(client, system, monkeypatch):
    def fail_delivery(recipient, otp):
        raise smtplib.SMTPAuthenticationError(535, b"rejected")

    monkeypatch.setattr(auth_controller, "_send_otp_email", fail_delivery)

    response = start_login(client)

    assert b"Could not send the verification email" in response.data
    assert "A101" not in system.otp_records
    with client.session_transaction() as session:
        assert "pending_rollno" not in session
        assert "rollno" not in session


def test_missing_registered_email_does_not_send_code(client, system):
    system.students["A101"]["email"] = ""

    response = start_login(client)

    assert b"could not send a verification code" in response.data.lower()
    assert system.sent_emails == []
    assert "A101" not in system.otp_records


def test_verification_without_pending_challenge_is_rejected(client):
    response = client.post("/verify_otp", data={"otp": "123456"})

    assert b"OTP expired" in response.data


def test_json_verify_response_does_not_include_otp(client, system):
    start_login(client)
    code = system.sent_emails[-1]["otp"]

    response = client.post("/verify_otp", json={"otp": code})

    assert response.status_code == 200
    assert response.json == {"success": True, "message": "OTP verified"}


def test_smtp_adapter_formats_email_and_uses_requested_recipient(monkeypatch):
    instances = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.message = None
            self.tls_started = False
            instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            self.tls_started = True

        def login(self, username, password):
            assert username == "test-sender@example.test"
            assert password == "dummy-app-password"

        def send_message(self, message):
            self.message = message

    monkeypatch.setenv("MAIL_USERNAME", "test-sender@example.test")
    monkeypatch.setenv("MAIL_PASSWORD", "dummy-app-password")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "test-sender@example.test")
    monkeypatch.setattr(auth_controller.smtplib, "SMTP", FakeSMTP)
    assert auth_controller._send_otp_email("student.b@example.test", "123456") is True

    smtp = instances[0]
    assert (smtp.host, smtp.port, smtp.timeout) == ("smtp.gmail.com", 587, 10)
    assert smtp.tls_started is True
    assert smtp.message["To"] == "student.b@example.test"
    assert smtp.message["Subject"] == "Your College Voting System OTP"
    assert "123456" in smtp.message.get_content()
    assert "5 minutes" in smtp.message.get_content()
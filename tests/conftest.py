from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import app as voting_app
from controllers import admin as admin_controller
from controllers import auth as auth_controller
from controllers import results as results_controller
from controllers import voting as voting_controller


class FakeBlockchain:
    def __init__(self):
        self.chain = [SimpleNamespace(
            index=0,
            transactions=[],
            timestamp="test-time",
            previous_hash="0",
            nonce=0,
            hash="test-genesis-hash",
        )]
        self.pending_transactions = []
        self.mined = 0
        self.saved = 0

    def new_transaction(self, position, candidate, ballot_id=None):
        self.pending_transactions.append({
            "position": position,
            "candidate": candidate,
            "ballot_id": ballot_id,
            "timestamp": "test-time",
        })
        return len(self.pending_transactions) - 1

    def mine_pending_transactions(self, miner_address="admin"):
        if self.pending_transactions:
            self.chain.append(SimpleNamespace(transactions=list(self.pending_transactions)))
            self.pending_transactions.clear()
            self.mined += 1

    def save(self):
        self.saved += 1

    def is_chain_valid(self):
        return True

    def to_dict(self):
        return {"chain": [{
            "index": block.index,
            "transactions": block.transactions,
            "timestamp": block.timestamp,
            "previous_hash": block.previous_hash,
            "nonce": block.nonce,
            "hash": block.hash,
        } for block in self.chain]}


@pytest.fixture
def system(monkeypatch):
    students = {
        "A101": {
            "rollno": "A101",
            "mobile": "1111111111",
            "email": "student.a@example.test",
            "password": "password-a",
            "name": "Student A",
            "approved": True,
            "voted": 0,
        },
        "B202": {
            "rollno": "B202",
            "mobile": "2222222222",
            "email": "student.b@example.test",
            "password": "password-b",
            "name": "Student B",
            "approved": True,
            "voted": 0,
        },
    }
    otp_records = {}
    sent_emails = []
    ballots = {}
    login_attempts = {}
    settings = {"voting_open": "true", "results_released": "false"}
    candidates = {position: [] for position in voting_app.ALLOWED_POSITIONS}

    def validate_login(rollno, mobile, password):
        student = students.get(rollno)
        if not student or student["password"] != password:
            return None
        if mobile and student["mobile"] != mobile:
            return None
        return deepcopy(student)

    def get_user_by_rollno(rollno):
        student = students.get(rollno)
        return deepcopy(student) if student else None

    def store_otp(rollno, otp_hash, expires_at, sent_at=None, resend_count=0):
        otp_records[rollno] = {
            "otp_hash": otp_hash,
            "expires_at": expires_at,
            "sent_at": sent_at or datetime.now(timezone.utc),
            "resend_count": resend_count,
            "attempts": 0,
        }

    def send_email(recipient, otp):
        sent_emails.append({"recipient": recipient, "otp": otp})
        return True

    def add_candidate(name, symbol, position, image=None):
        if any(
            candidate["symbol"] == symbol or candidate["name"] == name
            for candidate in candidates.get(position, [])
        ):
            return False
        candidates[position].append({
            "name": name,
            "symbol": symbol,
            "position": position,
            "image": image,
        })
        return True

    def cast_ballot(rollno, choices):
        if rollno in ballots:
            return False
        ballots[rollno] = deepcopy(choices)
        return True

    def is_login_rate_limited(identifier, max_attempts=5):
        return login_attempts.get(identifier, 0) >= max_attempts

    def record_failed_login(identifier, lockout_seconds=120):
        login_attempts[identifier] = login_attempts.get(identifier, 0) + 1

    def reset_login_attempts(identifier):
        login_attempts.pop(identifier, None)

    monkeypatch.setattr(auth_controller, "validate_login", validate_login)
    monkeypatch.setattr(auth_controller, "is_user_approved", lambda rollno: bool(students.get(rollno, {}).get("approved")))
    monkeypatch.setattr(voting_controller, "is_user_approved", lambda rollno: bool(students.get(rollno, {}).get("approved")))
    monkeypatch.setattr(voting_controller, "get_user_by_rollno", get_user_by_rollno)
    monkeypatch.setattr(auth_controller, "get_user_email", lambda rollno: students.get(rollno, {}).get("email", ""))
    monkeypatch.setattr(auth_controller, "store_otp", store_otp)
    monkeypatch.setattr(auth_controller, "get_otp", lambda rollno: deepcopy(otp_records.get(rollno)))
    monkeypatch.setattr(auth_controller, "delete_otp", lambda rollno: otp_records.pop(rollno, None))
    monkeypatch.setattr(
        auth_controller,
        "increment_otp_attempts",
        lambda rollno: otp_records[rollno].__setitem__("attempts", otp_records[rollno]["attempts"] + 1),
    )
    monkeypatch.setattr(auth_controller, "_send_otp_email", send_email)
    monkeypatch.setattr(auth_controller, "is_login_rate_limited", is_login_rate_limited)
    monkeypatch.setattr(auth_controller, "record_failed_login", record_failed_login)
    monkeypatch.setattr(auth_controller, "reset_login_attempts", reset_login_attempts)
    monkeypatch.setattr(auth_controller, "user_exists", lambda rollno: rollno in students)
    monkeypatch.setattr(auth_controller, "register_user", lambda *args, **kwargs: True)
    for controller in (admin_controller, results_controller, voting_controller):
        monkeypatch.setattr(controller, "get_setting", lambda key: settings.get(key))
    monkeypatch.setattr(admin_controller, "update_setting", lambda key, value: settings.__setitem__(key, value))
    monkeypatch.setattr(voting_controller, "get_candidates_by_position", lambda position: deepcopy(candidates.get(position, [])))
    monkeypatch.setattr(
        voting_controller,
        "is_valid_candidate",
        lambda position, name: name == "NOTA" or any(item["name"] == name for item in candidates.get(position, [])),
    )
    monkeypatch.setattr(voting_controller, "has_voted", lambda rollno: rollno in ballots)
    monkeypatch.setattr(voting_controller, "cast_ballot", cast_ballot)
    monkeypatch.setattr(results_controller, "get_results", lambda position: [])
    monkeypatch.setattr(voting_controller, "add_candidate", add_candidate)
    monkeypatch.setattr(admin_controller, "approve_user_by_rollno", lambda rollno: students.get(rollno, {}).update(approved=True))
    monkeypatch.setattr(admin_controller, "delete_user", lambda rollno: students.pop(rollno, None))
    monkeypatch.setattr(admin_controller, "get_all_users", lambda: [deepcopy(student) for student in students.values()])
    monkeypatch.setattr(admin_controller, "get_pending_users", lambda: [deepcopy(student) for student in students.values() if not student["approved"]])
    monkeypatch.setattr(admin_controller, "clear_all_candidates", lambda: [items.clear() for items in candidates.values()])
    fake_blockchain = FakeBlockchain()
    monkeypatch.setitem(voting_app.app.extensions, "blockchain", fake_blockchain)
    monkeypatch.setenv("MAIL_USERNAME", "test-sender@example.test")
    monkeypatch.setenv("MAIL_PASSWORD", "not-a-real-password")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "test-sender@example.test")
    monkeypatch.setitem(voting_app.app.config, "TESTING", True)

    return SimpleNamespace(
        students=students,
        otp_records=otp_records,
        sent_emails=sent_emails,
        ballots=ballots,
        login_attempts=login_attempts,
        settings=settings,
        candidates=candidates,
        blockchain=fake_blockchain,
    )


@pytest.fixture
def client(system):
    return voting_app.app.test_client()


@pytest.fixture
def signed_in_student(client):
    with client.session_transaction() as session:
        session["rollno"] = "A101"
    return client


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as session:
        session["admin"] = True
    return client
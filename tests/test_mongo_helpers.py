from unittest.mock import MagicMock

import pytest
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
from werkzeug.security import generate_password_hash

from database import mongo_db


def test_database_connection_success_initializes_indexes(monkeypatch):
    fake_database = MagicMock()
    fake_client = MagicMock()
    fake_client.__getitem__.return_value = fake_database
    monkeypatch.setattr(mongo_db, "_client", None)
    monkeypatch.setattr(mongo_db, "_database", None)
    monkeypatch.setattr(mongo_db, "MongoClient", lambda *args, **kwargs: fake_client)

    result = mongo_db.get_database()

    assert result is fake_database
    fake_client.admin.command.assert_called_once_with("ping")
    fake_database.otp_codes.create_index.assert_called_once_with("expires_at", expireAfterSeconds=0)


def test_database_connection_failure_raises_safe_error(monkeypatch):
    fake_client = MagicMock()
    fake_client.admin.command.side_effect = ServerSelectionTimeoutError("unavailable")
    monkeypatch.setattr(mongo_db, "_client", None)
    monkeypatch.setattr(mongo_db, "_database", None)
    monkeypatch.setattr(mongo_db, "MongoClient", lambda *args, **kwargs: fake_client)

    with pytest.raises(mongo_db.MongoConnectionError) as error:
        mongo_db.get_database()

    assert "Could not connect to MongoDB" in str(error.value)
    assert "unavailable" not in str(error.value)
    fake_client.close.assert_called_once()


def test_student_retrieval_removes_password_and_internal_id(monkeypatch):
    database = MagicMock()
    database.users.find_one.return_value = {
        "_id": "internal-id",
        "rollno": "A101",
        "password": "hashed-value",
        "name": "Student A",
        "approved": True,
    }
    database.votes.find_one.return_value = None
    monkeypatch.setattr(mongo_db, "_database", database)

    student = mongo_db.get_user_by_rollno("A101")

    assert student["rollno"] == "A101"
    assert student["id"] == "A101"
    assert student["voted"] == 0
    assert "password" not in student
    assert "_id" not in student


def test_missing_student_returns_none(monkeypatch):
    database = MagicMock()
    database.users.find_one.return_value = None
    monkeypatch.setattr(mongo_db, "_database", database)

    assert mongo_db.get_user_by_rollno("missing") is None


def test_login_accepts_valid_hash_and_optional_mobile(monkeypatch):
    database = MagicMock()
    database.users.find_one.return_value = {
        "_id": "student-id",
        "rollno": "A101",
        "mobile": "1111111111",
        "password": generate_password_hash("correct-password"),
    }
    monkeypatch.setattr(mongo_db, "_database", database)

    result = mongo_db.validate_login("A101", "", "correct-password")

    assert result["rollno"] == "A101"
    database.users.find_one.assert_called_once_with({"rollno": "A101"})


def test_wrong_password_is_rejected(monkeypatch):
    database = MagicMock()
    database.users.find_one.return_value = {
        "_id": "student-id",
        "rollno": "A101",
        "password": generate_password_hash("correct-password"),
    }
    monkeypatch.setattr(mongo_db, "_database", database)

    assert mongo_db.validate_login("A101", "", "wrong-password") is None


def test_cast_ballot_persists_record_and_marks_student_voted(monkeypatch):
    database = MagicMock()
    database.users.find_one.return_value = None
    monkeypatch.setattr(mongo_db, "_database", database)
    choices = {"President": "Candidate A"}

    assert mongo_db.cast_ballot("A101", choices) is True

    inserted = database.votes.insert_one.call_args.args[0]
    assert inserted["rollno"] == "A101"
    assert inserted["choices"] == choices
    database.users.update_one.assert_called_once_with(
        {"rollno": "A101"}, {"$set": {"voted": 1}}
    )


def test_duplicate_ballot_is_rejected(monkeypatch):
    database = MagicMock()
    database.users.find_one.return_value = None
    database.votes.insert_one.side_effect = DuplicateKeyError("duplicate")
    monkeypatch.setattr(mongo_db, "_database", database)

    assert mongo_db.cast_ballot("A101", {"President": "Candidate A"}) is False
    database.users.update_one.assert_not_called()
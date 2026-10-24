import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash


_client = None
_database = None


class MongoConnectionError(RuntimeError):
    pass


def get_database():
    global _client, _database

    if _database is None:
        uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
        database_name = os.getenv("MONGO_DB_NAME", "college_voting")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
        try:
            _client.admin.command("ping")
        except PyMongoError as error:
            _client.close()
            _client = None
            raise MongoConnectionError(
                "Could not connect to MongoDB. Start the local server or check MONGO_URI."
            ) from error
        _database = _client[database_name]
        initialize_database()
    return _database


def initialize_database():
    database = _database
    if database is None:
        return
    database.users.create_index([("rollno", ASCENDING)], unique=True)
    database.candidates.create_index(
        [("position", ASCENDING), ("symbol", ASCENDING)], unique=True
    )
    database.candidates.create_index(
        [("position", ASCENDING), ("name", ASCENDING)], unique=True
    )
    database.votes.create_index([("rollno", ASCENDING)], unique=True)
    database.settings.create_index([("key", ASCENDING)], unique=True)
    database.otp_codes.create_index("expires_at", expireAfterSeconds=0)
    database.login_attempts.create_index("expires_at", expireAfterSeconds=0)


def _now():
    return datetime.now(timezone.utc)


def _user_for_template(user):
    if user is None:
        return None
    user = dict(user)
    user["id"] = user.get("rollno", str(user.get("_id", "")))
    user["voted"] = 1 if (
        user.get("voted") == 1
        or get_database().votes.find_one({"rollno": user["rollno"]})
    ) else 0
    user["approved"] = int(bool(user.get("approved", False)))
    user.pop("password", None)
    user.pop("_id", None)
    return user


def create_users_table():
    get_database().users.create_index([("rollno", ASCENDING)], unique=True)


def create_candidates_table():
    get_database().candidates.create_index(
        [("position", ASCENDING), ("symbol", ASCENDING)], unique=True
    )
    get_database().candidates.create_index(
        [("position", ASCENDING), ("name", ASCENDING)], unique=True
    )


def create_votes_table():
    get_database().votes.create_index([("rollno", ASCENDING)], unique=True)


def create_settings_table():
    get_database().settings.create_index([("key", ASCENDING)], unique=True)


def symbol_exists(position, symbol):
    return get_database().candidates.find_one({"position": position, "symbol": symbol})


def add_candidate(name, symbol, position, image=None):
    try:
        get_database().candidates.insert_one({
            "name": name,
            "symbol": symbol,
            "position": position,
            "image": image,
        })
    except DuplicateKeyError:
        return False
    return True


def user_exists(rollno):
    return get_database().users.find_one({"rollno": rollno})


def register_user(name, rollno, mobile, email, password, photo=None, approved=False):
    try:
        get_database().users.insert_one({
            "name": name,
            "rollno": rollno,
            "mobile": mobile,
            "email": email,
            "password": password,
            "voted": 0,
            "photo": photo,
            "approved": bool(approved),
        })
    except DuplicateKeyError:
        return False
    return True


def is_user_approved(rollno):
    user = get_database().users.find_one({"rollno": rollno}, {"approved": 1})
    return bool(user and user.get("approved"))


def approve_user_by_rollno(rollno):
    get_database().users.update_one({"rollno": rollno}, {"$set": {"approved": True}})


def delete_user(rollno):
    get_database().users.delete_one({"rollno": rollno})


def get_pending_users():
    return [_user_for_template(user) for user in get_database().users.find({"approved": {"$ne": True}})]


def get_all_users():
    return [_user_for_template(user) for user in get_database().users.find()]


def validate_login(rollno, mobile, password):
    database = get_database()
    query = {"rollno": rollno}
    if mobile:
        query["mobile"] = mobile
    user = database.users.find_one(query)
    if not user:
        return None

    stored_password = user.get("password", "")
    if stored_password.startswith(("scrypt:", "pbkdf2:")):
        valid = check_password_hash(stored_password, password)
    elif len(stored_password) == 64:
        valid = hmac.compare_digest(
            hashlib.sha256(password.encode()).hexdigest(), stored_password
        )
    else:
        valid = hmac.compare_digest(stored_password, password)

    if not valid:
        return None
    if not stored_password.startswith(("scrypt:", "pbkdf2:")):
        database.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"password": generate_password_hash(password)}},
        )
    return user


def get_user_by_rollno(rollno):
    return _user_for_template(get_database().users.find_one({"rollno": rollno}))


def get_user_email(rollno):
    user = get_database().users.find_one({"rollno": rollno}, {"email": 1})
    return user.get("email", "") if user else ""


def get_candidates_by_position(position):
    candidates = get_database().candidates.find({"position": position}).sort("name", ASCENDING)
    return [dict(candidate) for candidate in candidates]


def is_valid_candidate(position, candidate):
    if candidate == "NOTA":
        return True
    return bool(get_database().candidates.find_one({"position": position, "name": candidate}))


def has_voted(rollno):
    database = get_database()
    return bool(
        database.users.find_one({"rollno": rollno, "voted": 1}, {"_id": 1})
        or database.votes.find_one({"rollno": rollno}, {"_id": 1})
    )


def cast_ballot(rollno, choices):
    database = get_database()
    if database.users.find_one({"rollno": rollno, "voted": 1}, {"_id": 1}):
        return False
    try:
        database.votes.insert_one({
            "rollno": rollno,
            "choices": choices,
            "created_at": _now(),
        })
    except DuplicateKeyError:
        return False
    database.users.update_one({"rollno": rollno}, {"$set": {"voted": 1}})
    return True


def get_results(position):
    return list(get_database().votes.aggregate([
        {"$project": {"choice": {"$objectToArray": "$choices"}}},
        {"$unwind": "$choice"},
        {"$match": {"choice.k": position}},
        {"$group": {"_id": "$choice.v", "votes": {"$sum": 1}}},
        {"$project": {"_id": 0, "candidate": "$_id", "votes": 1}},
        {"$sort": {"votes": -1, "candidate": 1}},
    ]))


def get_setting(key):
    setting = get_database().settings.find_one({"key": key})
    return setting.get("value") if setting else None


def update_setting(key, value):
    get_database().settings.update_one(
        {"key": key}, {"$set": {"value": value}}, upsert=True
    )


def clear_all_candidates():
    get_database().candidates.delete_many({})


def is_login_rate_limited(identifier, max_attempts=5):
    record = get_database().login_attempts.find_one({
        "_id": identifier,
        "expires_at": {"$gt": _now()},
    })
    return bool(record and record.get("attempts", 0) >= max_attempts)


def record_failed_login(identifier, lockout_seconds=120):
    collection = get_database().login_attempts
    record = collection.find_one({"_id": identifier})
    expires_at = _now() + timedelta(seconds=lockout_seconds)
    if record and record.get("expires_at", _now()) <= _now():
        collection.replace_one(
            {"_id": identifier},
            {"attempts": 1, "expires_at": expires_at},
        )
    else:
        collection.update_one(
            {"_id": identifier},
            {"$inc": {"attempts": 1}, "$set": {"expires_at": expires_at}},
            upsert=True,
        )


def reset_login_attempts(identifier):
    get_database().login_attempts.delete_one({"_id": identifier})


def store_otp(rollno, otp_hash, expires_at, sent_at=None, resend_count=0):
    get_database().otp_codes.replace_one(
        {"_id": rollno},
        {
            "otp_hash": otp_hash,
            "expires_at": expires_at,
            "sent_at": sent_at or _now(),
            "resend_count": resend_count,
            "attempts": 0,
        },
        upsert=True,
    )


def get_otp(rollno):
    return get_database().otp_codes.find_one({"_id": rollno})


def increment_otp_attempts(rollno):
    get_database().otp_codes.update_one({"_id": rollno}, {"$inc": {"attempts": 1}})


def delete_otp(rollno):
    get_database().otp_codes.delete_one({"_id": rollno})
import argparse
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from database.mongo_db import get_database


def read_rows(connection, table):
    try:
        return connection.execute(f"SELECT * FROM {table}").fetchall()
    except sqlite3.OperationalError:
        return []


def migrate(sqlite_path):
    database = get_database()
    counts = {"users": 0, "candidates": 0, "ballots": 0, "settings": 0}

    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row

        for row in read_rows(connection, "users"):
            user = dict(row)
            user.pop("id", None)
            user["approved"] = bool(user.get("approved", 0))
            user["voted"] = int(bool(user.get("voted", 0)))
            database.users.update_one(
                {"rollno": user["rollno"]}, {"$setOnInsert": user}, upsert=True
            )
            counts["users"] += 1

        for row in read_rows(connection, "candidates"):
            candidate = dict(row)
            candidate.pop("id", None)
            result = database.candidates.update_one(
                {"position": candidate["position"], "symbol": candidate["symbol"]},
                {"$setOnInsert": candidate},
                upsert=True,
            )
            counts["candidates"] += int(result.upserted_id is not None)

        ballots = {}
        for row in read_rows(connection, "votes"):
            rollno = row["rollno"]
            ballots.setdefault(rollno, {})[row["position"]] = row["candidate"]
        for rollno, choices in ballots.items():
            database.votes.update_one(
                {"rollno": rollno},
                {"$setOnInsert": {"rollno": rollno, "choices": choices}},
                upsert=True,
            )
            database.users.update_one({"rollno": rollno}, {"$set": {"voted": 1}})
            counts["ballots"] += 1

        for row in read_rows(connection, "settings"):
            setting = dict(row)
            database.settings.update_one(
                {"key": setting["key"]}, {"$setOnInsert": setting}, upsert=True
            )
            counts["settings"] += 1

    return counts


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Copy SQLite voting data into MongoDB.")
    parser.add_argument("--sqlite", default="voting.db", help="Path to the SQLite database")
    args = parser.parse_args()
    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        parser.error(f"SQLite database not found: {sqlite_path}")

    counts = migrate(sqlite_path)
    print("Migration complete (existing MongoDB documents were left unchanged):")
    for collection, count in counts.items():
        print(f"  {collection}: {count}")


if __name__ == "__main__":
    main()
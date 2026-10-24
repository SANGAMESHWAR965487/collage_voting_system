# MongoDB setup

## Local MongoDB

1. Install and start MongoDB Community Server, or create a MongoDB Atlas cluster.
2. Open a terminal in `backend/` and install packages with `python -m pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` from `backend/`. Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"` and put the result in `SECRET_KEY`. Set a private admin password and phone number.
4. For a local server, keep the example `MONGO_URI`. For Atlas, set `MONGO_URI` to the cluster connection string, including a database user and password, and allow the machine's IP in Atlas Network Access.
5. Set `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER` in `.env` using a Gmail App Password. From `backend/`, start the app with `python app.py`. Student OTPs are sent to the email stored on each student's MongoDB user record.

## Existing SQLite data

Keep `backend/voting.db` as a backup. With MongoDB running and `.env` configured, run this from `backend/`:

```powershell
python migrate_sqlite_to_mongo.py --sqlite voting.db
```

The migration is repeatable and does not overwrite documents already present in MongoDB. It copies users, candidates, ballots, and settings. Check the reported counts and verify the records in MongoDB before retiring the SQLite file.

## Production notes

Set `FLASK_ENV=production`, use a strong stable `SECRET_KEY`, and keep `.env` out of source control. Use a Gmail App Password rather than the Gmail account password. OTPs expire after five minutes; resends are throttled. Run behind a production WSGI server with HTTPS, not Flask's development server.
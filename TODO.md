# Backend setup

See [MONGODB_SETUP.md](MONGODB_SETUP.md) for MongoDB configuration, dependency installation, and optional SQLite migration.

Admin credentials, Gmail SMTP credentials, and the Flask session key must be configured privately in `.env`; do not put real credentials in source files or documentation. Student login OTPs are delivered to the email stored on each MongoDB user record.

The blockchain is a tamper-evident demonstration ledger backed by a local JSON file. It is not immutable or sufficient as the sole integrity control for a real election.

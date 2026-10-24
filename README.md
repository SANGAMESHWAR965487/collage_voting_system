# College Voting System

A secure Flask college voting application using MongoDB for student accounts, candidates, voting records, and settings. It includes voter authentication, email OTP verification, candidate management, and electronic voting.

## Application Structure

The project separates HTTP handling, persistence, and presentation:

- `controllers/` contains Flask blueprints for authentication, administration, results, voting, and blockchain requests.
- `database/` contains the persistence layer used by those controllers.
- `templates/` contains the Jinja views rendered for each request.
- `static/` contains stylesheets and uploaded images.
- `app.py` configures the Flask application, registers the controllers, and remains the command-line entry point.

## Requirements

- Python 3.8 or newer
- MongoDB Atlas or a local MongoDB server
- A Gmail account with 2-Step Verification enabled and an App Password

## Setup

Open PowerShell in the project directory and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the values. Keep `.env` private; it is excluded by `.gitignore`.

```env
MONGO_URI=your_mongodb_connection_string
MONGO_DB_NAME=college_voting
SECRET_KEY=your_long_random_flask_secret
ADMIN_ID=admin
ADMIN_PHONE=your_admin_phone
ADMIN_PASSWORD=your_private_admin_password
MAIL_USERNAME=yourgmail@gmail.com
MAIL_PASSWORD=your_gmail_app_password
MAIL_DEFAULT_SENDER=yourgmail@gmail.com
FLASK_ENV=development
FLASK_DEBUG=false
```

For MongoDB Atlas, use the cluster connection string for `MONGO_URI` and allow your machine's IP address in Atlas Network Access. Generate a Flask secret with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

For a Gmail App Password, enable 2-Step Verification in your Google Account, then go to **Security → App passwords** and generate a password for this application. Put the generated App Password in `MAIL_PASSWORD`; do not use your normal Gmail password.

## Run

```powershell
python app.py
```

Open the local URL printed by Flask in your terminal. To check the configured MongoDB connection separately, run:

```powershell
python test_mongodb.py
```

## Student Login And OTP

Students enter their roll number and password. After MongoDB validates the credentials and the account is approved, the system sends a six-digit OTP to that student's email address stored in the MongoDB user record. The student must verify the OTP before the authenticated session is created and access to `/vote` is allowed.

OTP codes expire after five minutes, are stored in MongoDB only as hashes, and can be used once. Resending creates a new code; resend requests have a 60-second cooldown and are limited to three per login challenge. Student records need a valid `email` value and must be approved by an administrator.

To check delivery for two accounts, log in with Student A's roll number and password, verify the code sent to Student A's registered email, then repeat with Student B. Confirm each message arrives at the address on that particular student's MongoDB record. Do not place OTPs or mail credentials in source code or logs.

See [MONGODB_SETUP.md](MONGODB_SETUP.md) for MongoDB setup and existing data migration instructions.

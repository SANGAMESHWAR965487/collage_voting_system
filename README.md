# College Voting System

The repository is organized into two independent deployable projects:

## Frontend

All browser-facing files are in [`frontend/`](./frontend/):

- `index.html`, `app.js`, `config.js`, and `styles.css` are the standalone web client.
- `templates/` contains the existing Flask/Jinja page designs.
- `static/` contains styles and frontend assets, including the candidate image directory.

The standalone client calls the backend JSON API. Set `window.API_BASE_URL` in
[`frontend/config.js`](./frontend/config.js) to the deployed backend URL, without a
trailing slash.

## Backend

All Python application files are in [`backend/`](./backend/):

- `app.py` is the Flask application entry point.
- `controllers/` contains the page controllers and JSON API.
- `database/` contains MongoDB persistence operations.
- `blockchain.py` contains blockchain logic.
- `tests/` contains the automated tests.
- `requirements.txt` and `requirements-dev.txt` list Python dependencies.
- `docs/` contains MongoDB, testing, and project notes.

The Flask app locates templates and static assets in the sibling `frontend/` folder
when both projects are run from this repository. The standalone frontend uses its own
HTML, CSS, and JavaScript and does not require Flask to serve its pages.

## Local setup

In PowerShell from the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-dev.txt
Copy-Item backend\.env.example backend\.env
Set-Location backend
python app.py
```

Configure `backend/.env` with your MongoDB Atlas connection, stable `SECRET_KEY`, admin
credentials, Gmail App Password, and `FRONTEND_ORIGINS`. Keep `.env` private; it is
excluded by `.gitignore`. Generate a Flask secret with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

For local frontend development, serve the `frontend/` directory on
`http://localhost:5500` and include that exact origin in `FRONTEND_ORIGINS`.
See [`backend/docs/MONGODB_SETUP.md`](./backend/docs/MONGODB_SETUP.md) for database and
data migration instructions.

Run backend tests from the `backend/` directory:

```powershell
python -m pytest
```

## Vercel deployment

Create two Vercel projects connected to this repository:

1. **Backend:** set Root Directory to `backend`. Vercel deploys `app.py` as the Flask
   application. Add the environment variables listed in `backend/.env.example`; set
   `FLASK_ENV=production` and `FRONTEND_ORIGINS` to the exact deployed frontend origin.
2. **Frontend:** set Root Directory to `frontend`, select the **Other** framework preset,
   and use `.` as the output directory with no build command. Set `API_BASE_URL` in
   `frontend/config.js` to the backend deployment URL, then redeploy the frontend.

Use custom frontend and backend domains under the same parent domain for session-cookie
compatibility; browsers may block third-party cookies between unrelated `*.vercel.app`
domains. Do not use a wildcard CORS origin.

Candidate uploads and blockchain JSON currently use local filesystem storage. Vercel's
serverless filesystem is not durable, so use persistent object storage and database-
backed blockchain persistence before relying on those features in production.

# Testing Guide

## Approach

The automated suite exercises the existing Flask routes and helper functions. MongoDB operations, login-attempt tracking, student records, OTP records, ballots, and Gmail delivery are replaced with in-memory fakes or mocks. Blockchain algorithm tests use temporary files; route tests use a fake blockchain. The suite does not send email, connect to Atlas, cast a production vote, or write to the repository's `blockchain.json`.

`pytest.ini` limits discovery to `tests/`. This is important because the existing root-level `test_mongodb.py` is a manual MongoDB ping script with top-level execution, not a pytest unit-test module.

## Test Environment

- Windows PowerShell
- Python 3.8 or newer; the suite was run with Python 3.13.2
- Runtime packages from `requirements.txt`
- Development test package from `requirements-dev.txt`
- Test credentials and emails are dummy values in fixtures
- Flask imports `.env` through the existing `load_dotenv()` call. Do not use production credentials for local test runs; the suite never prints secrets.

The application is imported for route tests, but all external database and mail calls used by tests are replaced. The separate `python test_mongodb.py` command uses the configured `MONGO_URI` to perform a real, read-only ping. Run it only when you intend to check that configured MongoDB instance; it is not part of pytest.

## Install Test Dependencies

From the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

If PowerShell blocks activation, allow it for the current terminal process only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

`requirements-dev.txt` includes the runtime requirements and pytest. Pytest is not added to production `requirements.txt`.

## Run Automated Tests

Run the entire isolated suite:

```powershell
python -m pytest
```

Run one test file:

```powershell
python -m pytest tests/test_otp.py
```

Run with verbose test names:

```powershell
python -m pytest -vv
```

Run one specific case:

```powershell
python -m pytest tests/test_otp.py::test_resend_limit_is_enforced -vv
```

The generated `.pytest_cache` is ignored by Git. No tests require a live student account, Gmail account, Atlas database, or production data.

## Manual Testing

Use a staging MongoDB database and test student records, not production election data.

1. Confirm each test student has a unique roll number, correct password, registered email, and `approved: true` in the MongoDB `users` collection.
2. Set Gmail SMTP variables in a local `.env` using a Gmail App Password. Never use the account's normal Gmail password.
3. Start the application with `python app.py` and use the local URL shown in the terminal.
4. Log in as Student A and confirm the OTP arrives at Student A's stored address. Verify it once; confirm reuse is rejected.
5. Repeat as Student B and confirm the OTP goes only to Student B's stored address.
6. Check a wrong code, a code older than five minutes, five failed attempts, resend cooldown, and the three-resend limit.
7. Confirm `/vote` redirects before successful OTP verification and that logout removes the session.
8. In a staging election, test one valid ballot, an invalid/missing selection, voting closed, and a repeated ballot. Confirm the MongoDB `votes` record and public blockchain view.
9. Use admin credentials to test candidate creation, approval/rejection, voting controls, and mining. Candidate update/delete routes are not implemented and should return 404.

The root `test_mongodb.py` script performs only a MongoDB ping and prints the database name. It does not test authentication or modify records.

## Interpreting Results

- `PASSED`: the assertion matched current code behavior in the isolated test environment.
- `FAILED`: the assertion did not match current behavior; inspect the failure before changing application code.
- `ERROR`: setup, collection, or test execution failed before the assertion completed.
- Manual/deployment checks marked not tested require the relevant real environment and are not implied to pass by pytest.

The current automated report is in [TEST_REPORT.md](TEST_REPORT.md). A passing mock test does not establish that Gmail credentials, Atlas network access, production data, or a deployment provider are configured correctly.

## Security Considerations

- Do not print, commit, or paste `MONGO_URI`, `SECRET_KEY`, Gmail credentials, admin passwords, student passwords, or OTPs.
- Do not run manual vote tests against a production election database.
- Do not use real email addresses in automated tests; SMTP is replaced with a fake client.
- Keep `.env` local and confirm it remains excluded by `.gitignore`.
- Use a separate Atlas database and throwaway student records for manual integration checks.
- `app.py` uses `blockchain.json` and upload directories on the local filesystem. Back up and validate persistence before deploying to an ephemeral filesystem.

## Deployment Checklist

These are checks to perform after a provider-specific deployment has been configured. They have not been run from this repository.

### Render

- [ ] Configure all required MongoDB, Flask secret, admin, and Gmail variables in the Render environment dashboard; do not upload `.env`.
- [ ] Configure a production WSGI start command and install its WSGI server dependency; the current `requirements.txt` does not include one.
- [ ] Confirm Atlas network access permits the deployed service and verify a read-only database ping.
- [ ] Confirm outbound Gmail SMTP on port 587 with STARTTLS is allowed and test only with a test student.
- [ ] Confirm HTTPS is active so the production `Secure` session-cookie setting works.
- [ ] Configure durable storage or an external store for `blockchain.json` and uploaded files; verify writes survive a restart.
- [ ] Run login, OTP expiry/resend, vote-on-staging, admin authorization, logout, and blockchain tampering checks against staging.

### Vercel

- [ ] Treat deployment as blocked until a Vercel-compatible Python/Flask entry point and routing configuration are added; neither is present in this repository.
- [ ] Confirm whether the selected runtime supports the application's SMTP workflow and configure all secrets in the provider dashboard.
- [ ] Replace or provide durable storage for `blockchain.json` and uploads; serverless local filesystems must not be assumed persistent.
- [ ] Verify Atlas network access, production HTTPS cookies, request/runtime limits, OTP delivery, and staging-only voting before enabling real users.
- [ ] Do not declare Vercel support based only on local pytest results.
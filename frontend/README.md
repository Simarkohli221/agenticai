# Banking Investigation Agent — Streamlit Frontend

A lightweight Streamlit UI that acts purely as an API client for the
existing FastAPI backend. It never touches the database directly and
never makes an authorization decision itself — every security and
business rule is enforced by the backend; this app only calls the
backend's HTTP endpoints and displays what it returns.

## Prerequisites

This project uses a single Python virtual environment at the repo
root (`venv/`). The frontend reuses that same environment — there is
no separate virtual environment for the frontend.

## 1. Activate the existing virtual environment

From the repository root:

**Windows (PowerShell / cmd):**
```
venv\Scripts\activate
```

**Windows (Git Bash) / macOS / Linux:**
```
source venv/Scripts/activate    # Git Bash on Windows
source venv/bin/activate        # macOS / Linux
```

## 2. Install frontend requirements

```
pip install -r frontend/requirements.txt
```

(The backend's own dependencies, in the root `requirements.txt`, must
already be installed for the API to run — see the root README/steps
for backend setup.)

## 3. Start the backend (Terminal 1)

From the repository root, with the venv activated:

```
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` (Swagger docs
at `http://localhost:8000/docs`).

## 4. Start the frontend (Terminal 2)

From the repository root, with the venv activated:

```
streamlit run frontend/app.py
```

Streamlit will open the UI in your browser, typically at
`http://localhost:8501`.

## Configuration

The frontend talks to the backend over HTTP using the `API_BASE_URL`
environment variable (defaults to `http://localhost:8000` if unset):

```
# Git Bash / macOS / Linux
API_BASE_URL=http://localhost:8000 streamlit run frontend/app.py

# Windows PowerShell
$env:API_BASE_URL = "http://localhost:8000"; streamlit run frontend/app.py
```

## Logging in

Log in with an existing user account (see the backend's test-user
scripts, e.g. `scripts/create_test_user.py`, for local development
accounts and their roles). The role returned by the backend
(`INVESTIGATOR`, `SUPERVISOR`, `ADMIN`) determines which sections of
the UI are shown:

- **All roles**: run investigations (natural-language requests for
  any account number).
- **SUPERVISOR / ADMIN**: additionally see the case approval/rejection
  view and the controlled account-status-update form.

The JWT issued at login is kept only in Streamlit's session state for
the life of the browser session — it is never written to disk.

## What this frontend does NOT do

- It does not connect to the SQLite database.
- It does not import SQLAlchemy or any backend model/service module.
- It does not decide risk levels, approvals, or account-status
  transitions — it only submits requests and displays the backend's
  response.

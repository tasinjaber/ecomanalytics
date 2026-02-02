## Firebolt Project

### What’s runnable here

- `scripts/generate_data.py`: generates CSVs into `dataset/`
- `scripts/create_tables.py`: connects to Firebolt, creates tables, inserts sample rows, runs test queries
- `scripts/load_dataset_to_firebolt.py`: loads your CSV dataset into Firebolt tables (replace/append)
- `dashboard/app.py`: Streamlit app (dashboard + data pipeline)
- `report/generate_report.py`: generates a standalone HTML report

### Why this is a “final application” (not just a demo)

This project implements an end-to-end **data application workflow**:

- **Ingest**: generate or upload CSV datasets (`dataset/*.csv`)
- **Validate + Load**: load to Firebolt with replace/append, chunked inserts, and row-count validation
- **Serve**: explore KPIs + charts via Streamlit dashboard
- **Deliver**: generate a standalone HTML report for sharing/submission

### Changing database credentials

This project connects to **Firebolt** from `scripts/create_tables.py`.

Set these environment variables (recommended) instead of hardcoding secrets:

- `FIREBOLT_SERVICE_ACCOUNT_ID` (required)
- `FIREBOLT_SERVICE_ACCOUNT_SECRET` (required)
- `FIREBOLT_ACCOUNT_NAME` (optional)
- `FIREBOLT_ENGINE_NAME` (optional)
- `FIREBOLT_DATABASE` (optional)

You can use `env.example` as a template.

### Running the project (Windows)

#### 1) Activate the virtual environment

```powershell
cd C:\firebolt_project
.\venv\Scripts\Activate.ps1
python --version
```

If PowerShell blocks activation, run this once (in an elevated PowerShell):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 2) Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

#### 2) Create a local `.env` file (recommended)

Create `C:\firebolt_project\.env` and fill in your real values (this file is ignored by git):

```text
FIREBOLT_SERVICE_ACCOUNT_ID=...
FIREBOLT_SERVICE_ACCOUNT_SECRET=...
FIREBOLT_ACCOUNT_NAME=...
FIREBOLT_ENGINE_NAME=...
FIREBOLT_DATABASE=...
```

Tip: you can copy the template:

```powershell
Copy-Item .\env.example .\.env
```

Then edit `.env` and replace the values.

#### 3) Run the scripts

Generate CSV data (optional):

```powershell
python .\scripts\generate_data.py
```

Create tables + insert sample rows + run test queries:

```powershell
python .\scripts\create_tables.py
```

### Running the dashboard (Streamlit)

Install deps (if you haven’t yet):

```powershell
python -m pip install -r .\requirements.txt
```

Start the dashboard:

```powershell
streamlit run .\dashboard\app.py
```

Inside the dashboard, open the **Data Pipeline** tab to:
- Generate CSVs
- Upload your own CSVs
- Load them into Firebolt (replace/append)
- See row counts + refresh KPIs instantly

### Frontend landing page (Next.js)

This project also includes a separate Next.js landing page UI in `frontend/`. It links to your Streamlit dashboard via a configurable URL.

Run it:

```powershell
cd C:\firebolt_project\frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

Configure CTA links by copying `frontend/env.example` to `frontend/.env.local` and editing:

- `NEXT_PUBLIC_DASHBOARD_URL` (example: `http://localhost:8501`)
- `NEXT_PUBLIC_TRIAL_URL` (default: `#pricing`)

### Authentication + Roles (Dashboard)

This project supports basic role-based access for the Streamlit UI:

- **Admin**: can access Data Pipeline + Clear DB
- **Analyst**: can access Data Pipeline (no Clear DB)
- **Viewer**: dashboard only (no Data Pipeline)

Setup:

1) Copy `config/users.example.json` → `config/users.json`
2) Create users with hashed passwords:

```powershell
python .\scripts\create_user.py --username admin --role Admin
```

#### Register in the UI (optional)

You can also register directly from the Streamlit sidebar (**Register** tab). New users are **Viewer** by default.

To allow creating Admin/Analyst accounts from the UI, set an invite code in `.env`:

```text
ADMIN_INVITE_CODE=choose_a_secret_code
```

#### Super Admin (always available)

If you want an Admin account that can log in even when `config/users.json` is missing, set:

```text
SUPER_ADMIN_USERNAME=admin
SUPER_ADMIN_PASSWORD_BCRYPT=replace_me
```

Generate the bcrypt hash with:

```powershell
python .\scripts\hash_password.py
```

### API Endpoints (FastAPI)

Set an API key, then run:

```powershell
$env:API_KEY="your_api_key"
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Authenticated endpoints require header: `X-API-Key: your_api_key`

- `GET /kpis`
- `GET /top-products?limit=10`
- `GET /top-pages?limit=10`

### Scheduled Pipelines (APScheduler)

Run the scheduler (incremental loads + alerts):

```powershell
python .\pipelines\scheduler.py
```

Env knobs (optional):
- `LOAD_EVERY_MIN` (default 30)
- `ALERTS_EVERY_MIN` (default 60)
- `LOAD_TABLES` (default `orders,order_items,page_views`)
- `LOAD_CHUNK_SIZE` (default 5000)

### Deployment (Docker)

Build:

```powershell
docker build -t firebolt-app .
```

Run (mount your `.env` + `config/users.json` into the container):

```powershell
docker run --rm -p 8501:8501 -p 8000:8000 `
  -v ${PWD}\.env:/app/.env `
  -v ${PWD}\config\users.json:/app/config/users.json `
  firebolt-app
```

Open dashboard: `http://localhost:8501`

### Generating a report (HTML)

This generates a standalone HTML report from your Firebolt tables:

```powershell
python .\report\generate_report.py
```

Output: `report\firebolt_report.html`

### Query Execution Proof (Analytical SQL)

Run 3 analytical queries (total sales, repeat customers, product-wise revenue):

```powershell
python .\scripts\analytics_queries.py
```

#### Windows PowerShell

```powershell
$env:FIREBOLT_SERVICE_ACCOUNT_ID="your_id"
$env:FIREBOLT_SERVICE_ACCOUNT_SECRET="your_secret"
$env:FIREBOLT_ACCOUNT_NAME="your_account"      # optional
$env:FIREBOLT_ENGINE_NAME="your_engine"        # optional
$env:FIREBOLT_DATABASE="your_database"         # optional

python .\scripts\create_tables.py
```

#### Windows CMD

```bat
set FIREBOLT_SERVICE_ACCOUNT_ID=your_id
set FIREBOLT_SERVICE_ACCOUNT_SECRET=your_secret
set FIREBOLT_ACCOUNT_NAME=your_account
set FIREBOLT_ENGINE_NAME=your_engine
set FIREBOLT_DATABASE=your_database

python .\scripts\create_tables.py
```



## Frontend (Next.js)

This is a teacher-friendly landing page UI for the project. It links to your Streamlit dashboard via a configurable URL.

### Run (Windows)

```powershell
cd C:\firebolt_project\frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

### Configure CTA URLs

Copy `frontend/env.example` to `frontend/.env.local` and edit:

- `NEXT_PUBLIC_DASHBOARD_URL`: where your Streamlit dashboard runs (example: `http://localhost:8501`)
- `NEXT_PUBLIC_TRIAL_URL`: where “Start Free Trial” should go (default: `#pricing`)



## Firebolt Analytics API (FastAPI)

### Run (Windows / PowerShell)

Set an API key (server-side):

```powershell
$env:API_KEY="your_api_key"
```

Run:

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Test

Health:

`GET /health`

Authenticated endpoints require header:

- `X-API-Key: your_api_key`

Endpoints:
- `GET /kpis`
- `GET /top-products?limit=10`
- `GET /top-pages?limit=10`



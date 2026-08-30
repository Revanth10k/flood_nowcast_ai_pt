# HydroAI — SIH 26085

Merged deployment:
- **Frontend:** the new Figma/React civic-tech UI.
- **Backend:** the existing FastAPI + GNN nowcast + NetworkX safe-routing engine.
- **Deployment:** one Render web service; the FastAPI service serves the compiled React app.
- Frontend API calls are same-origin (`/api/...`), so there are no localhost URLs in production.

## Local
```bash
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
uvicorn main:app --reload
```

## Render
The included `render.yaml` uses:
`pip install -r requirements.txt && cd frontend && npm install && npm run build`
and starts:
`uvicorn main:app --host 0.0.0.0 --port $PORT`

The municipal demo passcodes remain `sih2026` and `admin123`, as in the original frontend/backend.

from fastapi import FastAPI
from importlib.metadata import version as pkg_version

app = FastAPI(title="Diplomacy API")


@app.get("/api/health")
async def health():
    try:
        diplomacy_version = pkg_version("diplomacy")
    except Exception:
        diplomacy_version = "unknown"
    return {"status": "ok", "diplomacy_version": diplomacy_version}

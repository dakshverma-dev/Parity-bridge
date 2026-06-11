from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="ParityBridge Release Viewer")

@app.get("/", response_class=HTMLResponse)
def index():
    return "<h1>ParityBridge Benchmark Workbench</h1>"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/reports/latest")
def latest():
    return {"schemaVersion": "1.0.0"}

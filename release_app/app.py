from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="ParityBridge Release Viewer")

@app.get("/", response_class=HTMLResponse)
def index():
    return "<h1>ParityBridge Benchmark Workbench</h1>"

@app.get("/health")
def health():
    return {"status": "ok"}

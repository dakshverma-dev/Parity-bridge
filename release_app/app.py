from fastapi import FastAPI
app = FastAPI()

def _saved_runs(bundle_root):
    return []

@app.get("/compare")
def compare_page():
    return "<h1>Run Comparison</h1>"

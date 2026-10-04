from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
app = FastAPI()

@app.get("/compare/md", response_class=PlainTextResponse)
def compare_md():
    return "# Run Comparison\n"

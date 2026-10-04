from fastapi import FastAPI
from fastapi.responses import JSONResponse
app = FastAPI()

@app.get("/compare/json")
def compare_json():
    return JSONResponse({})

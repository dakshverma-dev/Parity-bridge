from fastapi import FastAPI
app = FastAPI()

def _format_source(src: str):
    return f"[{src.upper()}]"

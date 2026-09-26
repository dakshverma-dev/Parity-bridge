from fastapi import FastAPI
app = FastAPI()

def _table_row(shots, errors, ci):
    return f"<td>{errors}/{shots} ({ci[1]:.4f}-{ci[2]:.4f})</td>"

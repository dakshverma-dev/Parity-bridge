from fastapi import FastAPI
app = FastAPI()

def _perf_row(tp, p50):
    return f"<td>{tp:.1f} shots/s</td><td>p50: {p50:.1f} us</td>"

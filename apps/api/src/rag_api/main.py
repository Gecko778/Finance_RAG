from fastapi import FastAPI

app = FastAPI(title="Finance RAG API", version="0.1.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

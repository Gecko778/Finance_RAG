from fastapi import FastAPI

from rag_api.routes.documents import router as documents_router

app = FastAPI(title="Finance RAG API", version="0.1.0")
app.include_router(documents_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

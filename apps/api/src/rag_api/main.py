from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rag_core.settings import get_settings

from rag_api.routes.apikeys import router as apikeys_router
from rag_api.routes.auth import router as auth_router
from rag_api.routes.documents import router as documents_router
from rag_api.routes.kbs import router as kbs_router
from rag_api.routes.retrieval import router as retrieval_router

app = FastAPI(title="Finance RAG API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(apikeys_router)
app.include_router(kbs_router)
app.include_router(documents_router)
app.include_router(retrieval_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

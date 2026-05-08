from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ingestion, analytics, rag, stream
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# Setup CORS
# set to "*" for now will configure later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router)
app.include_router(analytics.router)
app.include_router(rag.router)
app.include_router(stream.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}

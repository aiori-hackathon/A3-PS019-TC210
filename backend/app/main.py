
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

app = FastAPI(
    title="PriVista API",
    description="Personal-Data Discovery and Privacy Evidence Inventory (technical evidence only)",
    version="2.0.0",
)


origins = os.getenv("PRIVISTA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def health_check():
    return {"status": "ok", "message": "PriVista backend is running"}

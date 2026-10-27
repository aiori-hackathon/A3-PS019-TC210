

import os
import threading
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()


_ready = threading.Event()
_load_error: dict = {}


def _load_api(app: FastAPI) -> None:
    try:
        from app.api.routes import router as api_router

        app.include_router(api_router, prefix="/api")
        _ready.set()
        print("PriVista API ready.")
    except Exception as e:
        _load_error["message"] = repr(e)
        traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_load_api, args=(app,), daemon=True).start()
    yield


app = FastAPI(
    title="PriVista API",
    description="Personal-Data Discovery and Privacy Evidence Inventory (technical evidence only)",
    version="2.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def wait_until_ready(request: Request, call_next):
    if request.url.path.startswith("/api") and not _ready.is_set():
        if _load_error:
            return JSONResponse({"detail": f"Backend failed to start: {_load_error['message']}"}, status_code=500)
        return JSONResponse({"detail": "Backend is starting up (loading the NLP model). Try again in a minute."},
                            status_code=503, headers={"Retry-After": "30"})
    return await call_next(request)


origins = os.getenv("PRIVISTA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    status = "ok" if _ready.is_set() else ("error" if _load_error else "starting")
    return {"status": status, "message": "PriVista backend is running", "ready": _ready.is_set()}


if __name__ == "__main__":
    import uvicorn

   
    port = os.getenv("X_ZOHO_CATALYST_LISTEN_PORT") or os.getenv("PORT") or "8000"
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(port))

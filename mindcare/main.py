from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mindcare.config import get_settings
from mindcare.routers import chat

app = FastAPI(title="MindCare API", version="0.1.0")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1")


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mindcare"}

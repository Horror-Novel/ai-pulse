from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routes import auth_routes, diagnostic, reports, dashboard
from .config import CORS_ORIGINS

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Pulse API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

app.include_router(auth_routes.router)
app.include_router(diagnostic.router)
app.include_router(reports.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok"}

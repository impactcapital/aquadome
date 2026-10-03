"""FastAPI application entry point for AquaDome."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import settings
from .routers import flights, entities, reports, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="AquaDome",
    description="Aerial drone analytics for waterway regulatory compliance",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(flights.router, prefix="/flights", tags=["flights"])
app.include_router(entities.router, prefix="/entities", tags=["entities"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routers import scrapper, usuarios, catalogo, partidas
from database import init_db
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="RetroArch API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True, # Cámbialo a True para mayor compatibilidad con custom schemes
    allow_methods=["*"],
    allow_headers=["*"],
)

#Con esto se puede acceder al contenido de /storage con: http://127.0.0.1:8000/storage/....
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

app.include_router(usuarios.router)
app.include_router(catalogo.router)
app.include_router(partidas.router)
app.include_router(scrapper.router)

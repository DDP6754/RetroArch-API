from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers import usuarios, catalogo, partidas
from database import init_db
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="RetroArch API", lifespan=lifespan)

#Con esto se puede acceder al contenido de /storage con: http://127.0.0.1:8000/storage/....
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

app.include_router(usuarios.router)
app.include_router(catalogo.router)
app.include_router(partidas.router)
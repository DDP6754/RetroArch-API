import os
import time
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import AsyncSessionLocal, Consola, Juego

router = APIRouter(tags=["Catalogo"])

UPLOAD_IMG_DIR = "./storage/covers"
UPLOAD_ROM_DIR = "./storage/roms"
os.makedirs(UPLOAD_IMG_DIR, exist_ok=True)
os.makedirs(UPLOAD_ROM_DIR, exist_ok=True)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/consolas")
async def listar_consolas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Consola))
    return result.scalars().all()

@router.get("/consolas/{consola_id}/juegos")
async def listar_juegos_por_consola(consola_id: int, db: AsyncSession = Depends(get_db)):
    res_juegos = await db.execute(select(Juego).filter(Juego.consola_id == consola_id))
    return res_juegos.scalars().all()

@router.get("/juegos/buscar")
async def buscar_juego(nombre: str = Query(..., min_length=2), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Juego).filter(Juego.juego.ilike(f"%{nombre}%")))
    return result.scalars().all()

@router.post("/juegos", status_code=status.HTTP_201_CREATED)
async def añadir_juego(
    titulo: str = Form(...),
    subtitulo: str = Form(...),
    consola_id: int = Form(...),
    perfil_id: int = Form(...),
    imagen_file: UploadFile = File(None, description="Imagen de carátula"),
    rom_file: UploadFile = File(None, description="Archivo de la ROM"),
    db: AsyncSession = Depends(get_db)
):
    """
    **Registrar un juego con su carátula y su archivo ROM.**
    Ambos archivos son opcionales, permitiendo crear la ficha primero y subir archivos después.
    """
    ruta_imagen = None
    ruta_rom = None
    timestamp = int(time.time())

    if imagen_file:
        ext_img = imagen_file.filename.split(".")[-1]
        nombre_img = f"cover_{timestamp}.{ext_img}"
        ruta_imagen = os.path.join(UPLOAD_IMG_DIR, nombre_img)
        with open(ruta_imagen, "wb") as f:
            f.write(await imagen_file.read())

    if rom_file:
        ext_rom = rom_file.filename.split(".")[-1]
        nombre_rom = f"{titulo.replace(' ', '_').lower()}_{timestamp}.{ext_rom}"
        ruta_rom = os.path.join(UPLOAD_ROM_DIR, nombre_rom)
        with open(ruta_rom, "wb") as f:
            f.write(await rom_file.read())

    nuevo_juego = Juego(
        juego=titulo, 
        Subtitulo=subtitulo, 
        consola_id=consola_id, 
        perfil_id=perfil_id,
        imagen=ruta_imagen,
        ruta_rom=ruta_rom
    )
    
    db.add(nuevo_juego)
    await db.commit()
    await db.refresh(nuevo_juego)
    
    return {"mensaje": "Juego y archivos subidos correctamente", "juego": nuevo_juego}
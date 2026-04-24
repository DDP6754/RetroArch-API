import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from pathlib import Path
from database import AsyncSessionLocal, Consola, Juego
import subprocess
import os
from .partidas import cargar_save

import shlex

router = APIRouter(tags=["Catalogo"])

UPLOAD_ROM_DIR = Path("./storage/roms")
UPLOAD_ROM_DIR.mkdir(parents=True, exist_ok=True)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/consolas")
async def listar_consolas(db: AsyncSession = Depends(get_db)):
    """
    **Obtener lista de consolas disponibles.**
    
    Usa este endpoint para llenar selectores o menús de sistemas. 
    Retorna objetos con el `id` necesario para asociar juegos y el nombre técnico en `console`.
    """
    result = await db.execute(select(Consola))
    return result.scalars().all()

@router.post("/consolas", status_code=status.HTTP_201_CREATED)
async def añadir_consola(
    nombre: str = Form(...),
    emulador: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    **Registrar una nueva consola en el sistema.**
    
    - **nombre**: Nombre identificador (ej: "gba", "n64"). Se guardará en minúsculas.
    - **emulador**: Nombre o ruta del núcleo/emulador que procesará esta consola.
    
    *Nota: Si el nombre ya existe, devolverá un error 400.*
    """
    res = await db.execute(select(Consola).where(Consola.console == nombre.lower()))
    if res.scalars().first():
        raise HTTPException(status_code=400, detail="La consola ya existe")

    nueva_consola = Consola(console=nombre.lower(), ruta_emulador=emulador)
    db.add(nueva_consola)
    await db.commit()
    await db.refresh(nueva_consola)
    return nueva_consola

@router.post("/juegos", status_code=status.HTTP_201_CREATED)
async def añadir_juego_manual(
    titulo: str = Form(...),
    consola_id: int = Form(...),
    perfil_id: int = Form(...),
    rom_file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db)
):
    """
    **Subir un juego manualmente desde el cliente.**
    
    Permite al usuario subir su propio archivo ROM (.gba, .nds, etc.) desde su dispositivo.
    - **titulo**: Nombre del juego para mostrar.
    - **consola_id**: ID de la consola a la que pertenece.
    - **perfil_id**: ID del usuario que lo está subiendo (lo hace "dueño").
    - **rom_file**: El archivo físico de la ROM.
    """
    ruta_rom = None
    timestamp = int(time.time())

    if rom_file:
        nombre_rom = f"rom_{timestamp}_{rom_file.filename}"
        dest_rom = UPLOAD_ROM_DIR / nombre_rom
        with open(dest_rom, "wb") as f:
            f.write(await rom_file.read())
        ruta_rom = f"/storage/roms/{nombre_rom}"

    nuevo_juego = Juego(
        juego=titulo, 
        consola_id=consola_id, 
        perfil_id=perfil_id,
        ruta_rom=ruta_rom
    )
    
    db.add(nuevo_juego)
    await db.commit()
    await db.refresh(nuevo_juego)
    return nuevo_juego

@router.get("/mi-biblioteca/{perfil_id}")
async def listar_mis_juegos_detallado(
    perfil_id: int, 
    search: Optional[str] = Query(None, description="Filtrar juegos por nombre"),
    db: AsyncSession = Depends(get_db)
):
    """
    ### Obtener Catálogo Personal del Usuario
    Recupera la lista de juegos vinculados a un perfil específico.

    **Parámetros:**
    - `perfil_id` (path): ID único del perfil/usuario.
    - `search` (query): [Opcional] Filtra los resultados por coincidencia parcial en el título (insensible a mayúsculas).

    **Comportamiento:**
    - Si se omite `search`, devuelve la biblioteca completa del usuario.
    - Si se incluye `search`, busca el patrón dentro de los nombres de los juegos.
    - Realiza un **JOIN** con la tabla de consolas para devolver el nombre del sistema.

    **Respuesta:**
    - Retorna un `Array` de objetos con `id`, `titulo`, `consola` y la `ruta` física del archivo.
    """
    query = (
        select(Juego)
        .options(joinedload(Juego.consola_rel))
        .where(Juego.perfil_id == perfil_id)
    )

    if search:
        query = query.where(Juego.juego.ilike(f"%{search}%"))

    result = await db.execute(query)
    juegos = result.scalars().all()
    
    return [
        {
            "id": j.id,
            "titulo": j.juego,
            "consola": j.consola_rel.console,
            "ruta": j.ruta_rom
        } for j in juegos
    ]

@router.delete("/juegos/desvincular/{juego_id}")
async def desvincular_juego(juego_id: int, perfil_id: int):
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Juego).where(Juego.id == juego_id, Juego.perfil_id == perfil_id)
        )
        juego_a_borrar = res.scalars().first()

        if not juego_a_borrar:
            raise HTTPException(status_code=404, detail="El juego no existe en tu biblioteca")

        ruta_archivo = juego_a_borrar.ruta_rom
        archivo_origen = juego_a_borrar.archivo_origen

        await db.delete(juego_a_borrar)
        await db.commit()

        res_otros = await db.execute(
            select(Juego).where(Juego.archivo_origen == archivo_origen)
        )
        otro_usuario_lo_tiene = res_otros.scalars().first()

        if not otro_usuario_lo_tiene:
            if ruta_archivo and os.path.exists(ruta_archivo):
                os.remove(ruta_archivo)

        return {
            "status": "success",
            "mensaje": f"Juego desvinculado de tu perfil"
        }

@router.get("/mi-biblioteca/{perfil_id}/{juego_id}")
async def listar_juego_perfil(
    juego_id: int, 
    perfil_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    ### Obtener Juego de Catálogo Personal del Usuario

    **Parámetros:**
    - `juego_id` (path): ID único del juego.
    - `perfil_id` (path): ID único del perfil.

    **Comportamiento:**
    - Obtiene el juego asociado a un perfil concreto

    **Respuesta:**
    - JSON asociado al juego de un perfil concreto
    """

    query = (
        select(Juego)
        .options(joinedload(Juego.consola_rel))
        .where(Juego.perfil_id == perfil_id)
        .where(Juego.id == juego_id)
    )
    result = await db.execute(query)
    juego = result.scalars().all()
    return juego

@router.get("/loadgame/{perfil_id}/{juego_id}")
async def load_game_retroarch(
    juego_id: int, 
    perfil_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    ### Lanza un juego determinado en un perfil con Retroarch con el save asociado.

    **Parámetros:**
    - `juego_id` (path): ID único del juego.
    - `perfil_id` (path): ID único del juego.

    **Comportamiento:**
    - Obtiene las rutas de rom y core del juego de un perfil e inicia Retroarch cargando el juego y sus saves

    **Respuesta:**
    - JSON del juego iniciado
    """
    juego = await listar_juego_perfil(juego_id, perfil_id, db)
    if juego:
        juego = juego[0]

        core = juego.consola_rel.ruta_emulador
        rom = juego.ruta_rom
        rom = shlex.quote(rom)
    else:
        raise HTTPException(status_code=404, detail="Item not found")

    if rom != None and core != None:

        await cargar_save(perfil_id, db)

        run_command = f"DISPLAY=:0 flatpak run org.libretro.RetroArch --config ./retroarch.cfg --appendconfig=./retro_overr.cfg -L {core} {rom}"
        print(run_command)
        subprocess.Popen(run_command, shell=True)
    else:
        raise HTTPException(status_code=404, detail="Item not found")

    return juego

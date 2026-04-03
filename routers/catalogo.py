import time
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pathlib import Path
from database import AsyncSessionLocal, Consola, Juego

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

    nueva_consola = Consola(console=nombre.lower(), emulador=emulador)
    db.add(nueva_consola)
    await db.commit()
    await db.refresh(nueva_consola)
    return nueva_consola

@router.get("/consolas/{consola_id}/juegos")
async def listar_juegos_por_consola(consola_id: int, db: AsyncSession = Depends(get_db)):
    """
    **Listar juegos filtrados por consola.**
    
    Muestra todos los juegos registrados bajo un ID de consola específico, sin importar a qué usuario pertenezcan. 
    Útil para vistas de administrador o catálogos globales.
    """
    res_juegos = await db.execute(select(Juego).filter(Juego.consola_id == consola_id))
    return res_juegos.scalars().all()

@router.get("/juegos/buscar")
async def buscar_juego(nombre: str = Query(..., min_length=2), db: AsyncSession = Depends(get_db)):
    """
    **Buscador global de juegos.**
    
    Realiza una búsqueda parcial (insensible a mayúsculas) en toda la base de datos.
    - **nombre**: El texto a buscar (mínimo 2 caracteres).
    """
    result = await db.execute(select(Juego).filter(Juego.juego.ilike(f"%{nombre}%")))
    return result.scalars().all()

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
async def listar_mis_juegos_detallado(perfil_id: int, db: AsyncSession = Depends(get_db)):
    """
    **Obtener la biblioteca privada del usuario.**
    
    Este es el endpoint principal para la vista de "Mis Juegos".
    Filtra la base de datos para devolver únicamente los juegos que pertenecen al `perfil_id` enviado.
    Incluye el nombre de la consola (`consola`) y la `ruta` directa para cargar la ROM en el emulador.
    """
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(Juego)
        .options(joinedload(Juego.consola_rel))
        .where(Juego.perfil_id == perfil_id)
    )
    juegos = result.scalars().all()
    
    return [
        {
            "id": j.id,
            "titulo": j.juego,
            "consola": j.consola_rel.console,
            "ruta": j.ruta_rom
        } for j in juegos
    ]
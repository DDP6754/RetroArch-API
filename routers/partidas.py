import os
from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import AsyncSessionLocal, Save, Savestate
import re

router = APIRouter(prefix="/partidas", tags=["Gestión de Partidas"])

UPLOAD_DIR = "./storage/games"
os.makedirs(f"{UPLOAD_DIR}/saves", exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/states", exist_ok=True)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.post("/save/{juego_id}", status_code=status.HTTP_201_CREATED)
async def subir_save(
    juego_id: int, 
    perfil_id: int, 
    archivo: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    """
    **Subir archivo de guardado (.srm).**

    Permite respaldar la memoria interna del juego (SRAM) en el servidor.
    - **juego_id**: ID del juego al que pertenece la partida.
    - **perfil_id**: ID del usuario que realiza el respaldo.
    - **archivo**: El archivo binario extraído del emulador.
    
    *El sistema genera automáticamente un nombre único basado en el usuario y el juego.*
    """
    # nombre_archivo = f"user_{perfil_id}_game_{juego_id}.srm"
    nombre_archivo = archivo.filename
    ruta_carpeta = f"./storage/saves/{perfil_id}"
    os.makedirs(ruta_carpeta, exist_ok=True)
    ruta_fisica = os.path.join(ruta_carpeta, nombre_archivo)
    
    with open(ruta_fisica, "wb") as buffer:
        content = await archivo.read()
        buffer.write(content)

    nuevo_save = Save(ruta_save=ruta_fisica, juego_id=juego_id, perfil_id=perfil_id)
    db.add(nuevo_save)
    await db.commit()
    return {"mensaje": "Save guardado", "ruta": ruta_fisica}

@router.post("/savestate/{juego_id}", status_code=status.HTTP_201_CREATED)
async def subir_savestate(
    juego_id: int, 
    perfil_id: int, 
    archivo: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    """
    **Subir estado de guardado rápido (.state).**

    Almacena una captura exacta del momento en que se detuvo el juego (Savestate).
    - **juego_id**: ID del juego relacionado.
    - **perfil_id**: ID del usuario propietario.
    - **archivo**: El archivo de estado generado por el núcleo del emulador.
    """
    nombre_archivo = f"user_{perfil_id}_game_{juego_id}.state"
    ruta_carpeta = "./storage/states"
    os.makedirs(ruta_carpeta, exist_ok=True)
    ruta_fisica = os.path.join(ruta_carpeta, nombre_archivo)
    
    with open(ruta_fisica, "wb") as buffer:
        content = await archivo.read()
        buffer.write(content)

    nuevo_state = Savestate(ruta_savestate=ruta_fisica, juego_id=juego_id, perfil_id=perfil_id)
    db.add(nuevo_state)
    await db.commit()
    return {"mensaje": "Savestate guardado", "ruta": ruta_fisica}

@router.get("/loadsave/{perfil_id}", status_code=status.HTTP_200_OK)
async def cargar_save(perfil_id: int, db: AsyncSession = Depends(get_db)):
    """
    **Establecer la ruta de saves para un usuario modificando retro_overr.cfg.**

    Devuelve el estado de la petición.
    """

    # user_save = await db.execute(select(Save).filter(Save.perfil_id == perfil_id))
    # if not user_save.scalars().all():
    #     print("No existe el save del perfil: ", user_save.scalars().all())
    with open("retro_overr.cfg", 'r') as f:
        file_data = f.read()
    file_data = re.sub('savefile_directory = "./storage/saves/\d/"', f'savefile_directory = "./storage/saves/{perfil_id}/"', file_data)
    print(file_data)
    with open("retro_overr.cfg", 'w') as f:
        f.write(file_data)

    return {"mensaje": "Save cargado"}


@router.get("/usuario/{perfil_id}/saves")
async def listar_mis_saves(perfil_id: int, db: AsyncSession = Depends(get_db)):
    """
    **Listar todos los archivos .srm de un usuario.**

    Devuelve una lista con todas las rutas de los archivos de guardado interno del usuario. 
    Sirve para que el frontend sepa qué partidas puede sincronizar al iniciar un juego.
    """
    result = await db.execute(select(Save).filter(Save.perfil_id == perfil_id))
    return result.scalars().all()

@router.get("/usuario/{perfil_id}/states")
async def listar_mis_states(perfil_id: int, db: AsyncSession = Depends(get_db)):
    """
    **Listar todos los .state de un usuario.**

    Recupera los puntos de guardado rápido disponibles para el perfil especificado. 
    Útil para mostrar un historial de "puntos de restauración" en la interfaz.
    """
    result = await db.execute(select(Savestate).filter(Savestate.perfil_id == perfil_id))
    return result.scalars().all()
'''
import os
from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import AsyncSessionLocal, Save, Savestate

router = APIRouter(prefix="/partidas", tags=["Gestión de Partidas"])

UPLOAD_DIR = "./storage/games"
os.makedirs(f"{UPLOAD_DIR}/saves", exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/states", exist_ok=True)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.post("/save/{juego_id}", status_code=status.HTTP_201_CREATED)
async def subir_save(
    juego_id: int, 
    perfil_id: int, 
    archivo: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    """
    **Subir archivo de guardado (.srm).**

    Permite respaldar la memoria interna del juego (SRAM) en el servidor.
    - **juego_id**: ID del juego al que pertenece la partida.
    - **perfil_id**: ID del usuario que realiza el respaldo.
    - **archivo**: El archivo binario extraído del emulador.
    
    *El sistema genera automáticamente un nombre único basado en el usuario y el juego.*
    """
    nombre_archivo = f"user_{perfil_id}_game_{juego_id}.srm"
    ruta_carpeta = "./storage/saves"
    os.makedirs(ruta_carpeta, exist_ok=True)
    ruta_fisica = os.path.join(ruta_carpeta, nombre_archivo)
    
    with open(ruta_fisica, "wb") as buffer:
        content = await archivo.read()
        buffer.write(content)

    nuevo_save = Save(ruta_save=ruta_fisica, juego_id=juego_id, perfil_id=perfil_id)
    db.add(nuevo_save)
    await db.commit()
    return {"mensaje": "Save guardado", "ruta": ruta_fisica}

@router.post("/savestate/{juego_id}", status_code=status.HTTP_201_CREATED)
async def subir_savestate(
    juego_id: int, 
    perfil_id: int, 
    archivo: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    """
    **Subir estado de guardado rápido (.state).**

    Almacena una captura exacta del momento en que se detuvo el juego (Savestate).
    - **juego_id**: ID del juego relacionado.
    - **perfil_id**: ID del usuario propietario.
    - **archivo**: El archivo de estado generado por el núcleo del emulador.
    """
    nombre_archivo = f"user_{perfil_id}_game_{juego_id}.state"
    ruta_carpeta = "./storage/states"
    os.makedirs(ruta_carpeta, exist_ok=True)
    ruta_fisica = os.path.join(ruta_carpeta, nombre_archivo)
    
    with open(ruta_fisica, "wb") as buffer:
        content = await archivo.read()
        buffer.write(content)

    nuevo_state = Savestate(ruta_savestate=ruta_fisica, juego_id=juego_id, perfil_id=perfil_id)
    db.add(nuevo_state)
    await db.commit()
    return {"mensaje": "Savestate guardado", "ruta": ruta_fisica}

@router.get("/usuario/{perfil_id}/saves")
async def listar_mis_saves(perfil_id: int, db: AsyncSession = Depends(get_db)):
    """
    **Listar todos los archivos .srm de un usuario.**

    Devuelve una lista con todas las rutas de los archivos de guardado interno del usuario. 
    Sirve para que el frontend sepa qué partidas puede sincronizar al iniciar un juego.
    """
    result = await db.execute(select(Save).filter(Save.perfil_id == perfil_id))
    return result.scalars().all()

@router.get("/usuario/{perfil_id}/states")
async def listar_mis_states(perfil_id: int, db: AsyncSession = Depends(get_db)):
    """
    **Listar todos los .state de un usuario.**

    Recupera los puntos de guardado rápido disponibles para el perfil especificado. 
    Útil para mostrar un historial de "puntos de restauración" en la interfaz.
    """
    result = await db.execute(select(Savestate).filter(Savestate.perfil_id == perfil_id))
    return result.scalars().all()
'''
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
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
    **Sincronizar archivo de guardado (.srm / .sav).**
    
    Sube el archivo de guardado persistente que genera el juego internamente.
    - **archivo**: El binario extraído del emulador.
    - **Retorna**: Confirmación y ruta del archivo almacenado.
    """
    nombre_archivo = f"user_{perfil_id}_game_{juego_id}.srm"
    ruta = os.path.join(f"{UPLOAD_DIR}/saves", nombre_archivo)
    
    with open(ruta, "wb") as buffer:
        content = await archivo.read()
        buffer.write(content)

    nuevo_save = Save(save=ruta, juego_id=juego_id, perfil_id=perfil_id)
    db.add(nuevo_save)
    await db.commit()
    return {"mensaje": "Save guardado", "ruta": ruta}

@router.post("/savestate/{juego_id}", status_code=status.HTTP_201_CREATED)
async def subir_savestate(
    juego_id: int, 
    perfil_id: int, 
    archivo: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    """
    **Sincronizar Savestate (Estado rápido).**
    
    Sube un punto de control rápido generado por el emulador.
    - **archivo**: El archivo de estado (ej: .state, .state1).
    """
    nombre_archivo = f"user_{perfil_id}_game_{juego_id}.state"
    ruta = os.path.join(f"{UPLOAD_DIR}/states", nombre_archivo)
    
    with open(ruta, "wb") as buffer:
        content = await archivo.read()
        buffer.write(content)

    nuevo_state = Savestate(savestate=ruta, juego_id=juego_id, perfil_id=perfil_id)
    db.add(nuevo_state)
    await db.commit()
    return {"mensaje": "Savestate guardado", "ruta": ruta}

@router.get("/usuario/{perfil_id}/saves")
async def listar_mis_saves(perfil_id: int, db: AsyncSession = Depends(get_db)):
    """**Obtener todos los archivos .srm del usuario.**"""
    result = await db.execute(select(Save).filter(Save.perfil_id == perfil_id))
    return result.scalars().all()

@router.get("/usuario/{perfil_id}/states")
async def listar_mis_states(perfil_id: int, db: AsyncSession = Depends(get_db)):
    """**Obtener todos los .state del usuario.**"""
    result = await db.execute(select(Savestate).filter(Savestate.perfil_id == perfil_id))
    return result.scalars().all()
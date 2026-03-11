from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import AsyncSessionLocal, Perfil

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def registrar_usuario(usuario: str, contrasena: str, db: AsyncSession = Depends(get_db)):
    """
    **Registro oficial de nuevos usuarios.**

    Este endpoint crea un perfil persistente en el sistema.
    - **usuario**: El nombre que usara el jugador para loguearse.
    - **contrasena**: Password en texto plano (se recomienda cifrar en el futuro).
    
    *Retorna el objeto del perfil con su ID generado por la base de datos.*
    """
    result = await db.execute(select(Perfil).filter(Perfil.usuario == usuario))
    existe = result.scalars().first()
    
    if existe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Este nombre de usuario ya esta registrado"
        )
    
    nuevo_perfil = Perfil(usuario=usuario, contraseña=contrasena)
    db.add(nuevo_perfil)
    await db.commit()
    await db.refresh(nuevo_perfil)
    
    return nuevo_perfil

@router.post("/login")
async def login(usuario: str, contrasena: str, db: AsyncSession = Depends(get_db)):
    """
    **Acceso de usuarios registrados.**

    Verifica que el nombre y la clave coincidan con un registro existente.
    - **Retorno**: Un JSON con el `usuario_id` necesario para peticiones privadas.
    """
    result = await db.execute(select(Perfil).filter(Perfil.usuario == usuario))
    user_db = result.scalars().first()
    
    if not user_db or user_db.contraseña != contrasena:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Credenciales incorrectas"
        )
    
    return {"mensaje": "Login exitoso", "usuario_id": user_db.id}

@router.get("/{usuario_id}")
async def obtener_perfil(usuario_id: int, db: AsyncSession = Depends(get_db)):
    """
    **Consulta de datos de perfil.**

    Muestra la informacion basica de un usuario segun su ID.
    """
    result = await db.execute(select(Perfil).filter(Perfil.id == usuario_id))
    perfil = result.scalars().first()
    
    if not perfil:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    return {"id": perfil.id, "usuario": perfil.usuario}
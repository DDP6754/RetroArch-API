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
    - **usuario**: El nombre único que usará el jugador para identificarse.
    - **contrasena**: Password para la cuenta (actualmente almacenada en texto plano).
    
    *Retorna el objeto del perfil con su ID generado automáticamente.*
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

    Punto de entrada principal para la autenticación.
    - **usuario / contrasena**: Credenciales enviadas por el usuario.
    
    **Uso en Frontend:** Es vital guardar el `usuario_id` devuelto en el almacenamiento local (localStorage o sessionStorage). 
    Este ID será necesario para todas las peticiones posteriores (descargar juegos, ver biblioteca o subir partidas).
    
    - **Retorno**: Un JSON con el mensaje de éxito y el `usuario_id`.
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

    Obtiene la información pública o básica de un usuario.
    - **usuario_id**: El identificador numérico único del perfil.
    """
    result = await db.execute(select(Perfil).filter(Perfil.id == usuario_id))
    perfil = result.scalars().first()
    
    if not perfil:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    return {"id": perfil.id, "usuario": perfil.usuario}
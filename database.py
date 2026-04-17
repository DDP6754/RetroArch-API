from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey

DATABASE_URL = "sqlite+aiosqlite:///./retroarch_cloud.db"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Perfil(Base):
    __tablename__ = "perfiles"
    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String, unique=True, index=True)
    contraseña = Column(String)
    
    juegos = relationship("Juego", back_populates="perfil_propietario")

class Consola(Base):
    __tablename__ = "consolas"
    id = Column(Integer, primary_key=True, index=True)
    console = Column(String, unique=True)
    ruta_emulador = Column(String, nullable=True)
    
    juegos = relationship("Juego", back_populates="consola_rel")

class Juego(Base):
    __tablename__ = "juegos"
    id = Column(Integer, primary_key=True, index=True)
    juego = Column(String)
    archivo_origen = Column(String, index=True)
    ruta_rom = Column(String)

    consola_id = Column(Integer, ForeignKey("consolas.id"))
    perfil_id = Column(Integer, ForeignKey("perfiles.id"))

    perfil_propietario = relationship("Perfil", back_populates="juegos")
    consola_rel = relationship("Consola", back_populates="juegos")

class Save(Base):
    __tablename__ = "saves"
    id = Column(Integer, primary_key=True, index=True)
    ruta_save = Column(String)
    
    juego_id = Column(Integer, ForeignKey("juegos.id"))
    perfil_id = Column(Integer, ForeignKey("perfiles.id"))

class Savestate(Base):
    __tablename__ = "savestates"
    id = Column(Integer, primary_key=True, index=True)
    ruta_savestate = Column(String)
    
    juego_id = Column(Integer, ForeignKey("juegos.id"))
    perfil_id = Column(Integer, ForeignKey("perfiles.id"))

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Base de datos sincronizada (Campos actualizados a ruta_).")
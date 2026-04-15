import asyncio
from sqlalchemy.future import select
from database import AsyncSessionLocal, Consola, init_db

# Definición de las consolas iniciales basadas en tu Scrapper
CONSOLAS_INICIALES = [
    {"console": "gba", "emulador": "mgba_libretro.so"},
    {"console": "ds", "emulador": "desmume_libretro.so"},
    {"console": "gamecube", "emulador": "dolphin_libretro.so"}
]

async def populate():
    # 1. Asegurarse de que las tablas existan
    print("Verificando tablas...")
    await init_db()

    async with AsyncSessionLocal() as db:
        print("Insertando consolas iniciales...")
        
        for data in CONSOLAS_INICIALES:
            # Verificar si la consola ya existe por su nombre técnico (console)
            query = await db.execute(
                select(Consola).where(Consola.console == data["console"])
            )
            existe = query.scalars().first()

            if not existe:
                nueva_consola = Consola(
                    console=data["console"],
                    ruta_emulador=data["emulador"]
                )
                db.add(nueva_consola)
                print(f" - Consola '{data['console']}' añadida.")
            else:
                print(f" - Consola '{data['console']}' ya existía, saltando...")

        await db.commit()
        print("\nBase de datos lista para usar.")

if __name__ == "__main__":
    asyncio.run(populate())
import asyncio
from sqlalchemy.future import select
from database import AsyncSessionLocal, Consola, init_db
CONSOLAS_INICIALES = [
    {"console": "gba", "emulador": "/ruta/emulador/gba"},
    {"console": "ds", "emulador": "/ruta/emulador/ds"},
    {"console": "gamecube", "emulador": "/ruta/emulador/gamecube"}
]

async def populate():
    print("Verificando tablas...")
    await init_db()

    async with AsyncSessionLocal() as db:
        print("Insertando consolas iniciales...")
        
        for data in CONSOLAS_INICIALES:
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

import zipfile
import httpx
from pathlib import Path
from urllib.parse import unquote
from sqlalchemy.future import select
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from database import AsyncSessionLocal, Juego, Consola

router = APIRouter(tags=["Scrapper"])

SISTEMAS_URLS = {
    "gba": "https://archive.org/download/GameboyAdvanceRomCollectionByGhostware/",
    "ds": "https://archive.org/download/nds_apfix/apfix/",
    "gamecube": "https://archive.org/download/gamecubecollectionbyblopez/"
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

@router.get("/scraper/listar/{sistema}")
async def listar_juegos_remotos(sistema: str):
    """
    **Obtener catálogo externo disponible para descargar.**
    
    Escanea los repositorios remotos (Archive.org) y devuelve una lista de juegos listos para ser bajados.
    - **sistema**: Debe ser 'gba', 'ds' o 'gamecube'.
    - **Retorno**: Un objeto con el nombre del juego, la URL de origen y el nombre del archivo real.
    """
    if sistema not in SISTEMAS_URLS:
        raise HTTPException(status_code=404, detail="Sistema no configurado")
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(SISTEMAS_URLS[sistema], headers=HEADERS)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
    juegos = []
    exts = [".zip", ".nds", ".gba", ".rvz", ".iso"]
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and any(href.lower().endswith(e) for e in exts) and not href.startswith(('?', '/')):
            juegos.append({
                "nombre": unquote(href).rsplit('.', 1)[0],
                "url_descarga": f"{SISTEMAS_URLS[sistema]}{href}",
                "archivo_real": href
            })
    return {"total": len(juegos), "juegos": juegos}

@router.websocket("/ws/descargar/{consola_nombre}")
async def websocket_descargar(websocket: WebSocket, consola_nombre: str):
    """
    **Gestor de descargas en tiempo real (WebSocket).**
    
    Maneja la descarga del juego, la descompresión y el registro en la base de datos.
    
    **Protocolo de comunicación:**
    1. El cliente se conecta y envía un JSON: 
       `{"url": "...", "nombre": "...", "perfil_id": ...}`
    2. El servidor responde con estados:
       - `{"status": "descargando", "progreso": 50.5}`
       - `{"status": "extrayendo", "mensaje": "..."}`
       - `{"status": "completado", "ruta_rom": "..."}`
       - `{"status": "error", "mensaje": "..."}`

    **Lógica Inteligente:**
    Si el archivo ya existe en el servidor (descargado por otro usuario), no se baja de nuevo; 
    simplemente se vincula al nuevo `perfil_id` para ahorrar espacio.
    """
    await websocket.accept()
    
    async with AsyncSessionLocal() as db:
        try:
            data = await websocket.receive_json()
            url_descarga = data.get("url")
            nombre_juego = data.get("nombre")
            perfil_id = data.get("perfil_id")

            res_c = await db.execute(
                select(Consola).where(Consola.console == consola_nombre.lower())
            )
            consola = res_c.scalars().first()
            if not consola:
                await websocket.send_json({"status": "error", "mensaje": f"La consola '{consola_nombre}' no existe."})
                return

            res_u = await db.execute(
                select(Juego).where(Juego.juego == nombre_juego, Juego.perfil_id == perfil_id)
            )
            if res_u.scalars().first():
                await websocket.send_json({"status": "error", "mensaje": "Ya tienes este juego en tu biblioteca."})
                return

            nombre_archivo_url = url_descarga.split('/')[-1]
            ruta_base = Path(f"./storage/roms/{consola_nombre}")
            ruta_base.mkdir(parents=True, exist_ok=True)

            res_f = await db.execute(
                select(Juego).where(Juego.ruta_rom.contains(nombre_archivo_url))
            )
            juego_previo = res_f.scalars().first()
            
            ruta_final = None

            if juego_previo and Path(juego_previo.ruta_rom).exists():
                ruta_final = juego_previo.ruta_rom
                await websocket.send_json({
                    "status": "descargando", 
                    "progreso": 100, 
                    "mensaje": "Archivo encontrado en el servidor. Vinculando..."
                })
            else:
                ext = nombre_archivo_url.split('.')[-1].lower()
                nombre_seguro = "".join(c for c in nombre_juego if c.isalnum() or c in (' ', '_', '-')).strip()
                ruta_temp = ruta_base / f"{nombre_seguro}.{ext}"

                async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                    async with client.stream("GET", url_descarga, headers=HEADERS) as r:
                        if r.status_code != 200:
                            await websocket.send_json({"status": "error", "mensaje": "Error de conexión con la fuente."})
                            return
                            
                        total = int(r.headers.get("Content-Length", 0))
                        descargado = 0
                        with open(ruta_temp, "wb") as f:
                            async for chunk in r.aiter_bytes(chunk_size=131072):
                                f.write(chunk)
                                descargado += len(chunk)
                                progreso = round((descargado / total) * 100, 2) if total > 0 else 0
                                await websocket.send_json({"status": "descargando", "progreso": progreso})

                ruta_final = str(ruta_temp)

                if ext == "zip":
                    await websocket.send_json({"status": "extrayendo", "mensaje": "Descomprimiendo..."})
                    try:
                        with zipfile.ZipFile(ruta_temp, 'r') as z:
                            z.extractall(ruta_base)
                            ruta_final = str(ruta_base / z.namelist()[0])
                        ruta_temp.unlink()
                    except Exception as e:
                        await websocket.send_json({"status": "error", "mensaje": f"Error al extraer: {str(e)}"})
                        return

            nuevo_registro = Juego(
                juego=nombre_juego,
                ruta_rom=str(ruta_final),
                consola_id=consola.id,
                perfil_id=perfil_id
            )
            
            db.add(nuevo_registro)
            await db.commit()
            
            await websocket.send_json({
                "status": "completado", 
                "mensaje": "Juego añadido a tu biblioteca.",
                "ruta_rom": str(ruta_final)
            })

        except WebSocketDisconnect:
            print("Cliente desconectado.")
        except Exception as e:
            await websocket.send_json({"status": "error", "mensaje": f"Error crítico: {str(e)}"})
        finally:
            await websocket.close()
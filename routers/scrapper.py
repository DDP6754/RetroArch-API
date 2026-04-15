import zipfile
import httpx
import os
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
    """Obtener catálogo externo disponible para descargar."""
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
    """WebSocket para descarga de juegos con progreso en MB y descompresión."""
    await websocket.accept()
    
    async with AsyncSessionLocal() as db:
        try:
            data = await websocket.receive_json()
            url_descarga = data.get("url")
            nombre_juego = data.get("nombre")
            perfil_id = data.get("perfil_id")

            res_c = await db.execute(select(Consola).where(Consola.console == consola_nombre.lower()))
            consola = res_c.scalars().first()
            if not consola:
                await websocket.send_json({"status": "error", "mensaje": f"Consola '{consola_nombre}' no existe."})
                return

            nombre_archivo_url = url_descarga.split('/')[-1]
            ruta_base = Path(f"./storage/roms/{consola_nombre}")
            ruta_base.mkdir(parents=True, exist_ok=True)
            
            ext = nombre_archivo_url.split('.')[-1].lower()
            nombre_seguro = "".join(c for c in nombre_juego if c.isalnum() or c in (' ', '_', '-')).strip()
            ruta_temp = ruta_base / f"{nombre_seguro}.{ext}"
            
            ruta_final = None

            async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                async with client.stream("GET", url_descarga, headers=HEADERS) as r:
                    if r.status_code != 200:
                        await websocket.send_json({"status": "error", "mensaje": "Error de conexión con la fuente."})
                        return
                    
                    total_bytes = int(r.headers.get("Content-Length", 0))
                    descargado_bytes = 0
                    
                    with open(ruta_temp, "wb") as f:
                        async for chunk in r.aiter_bytes(chunk_size=131072): # 128KB chunks
                            f.write(chunk)
                            descargado_bytes += len(chunk)
                            
                            # Cálculos de progreso y MB
                            progreso = round((descargado_bytes / total_bytes) * 100, 2) if total_bytes > 0 else 0
                            descargado_mb = round(descargado_bytes / (1024 * 1024), 2)
                            total_mb = round(total_bytes / (1024 * 1024), 2)

                            await websocket.send_json({
                                "status": "descargando", 
                                "progreso": progreso,
                                "descargado_mb": descargado_mb,
                                "total_mb": total_mb
                            })

            ruta_final = str(ruta_temp)


            if ext == "zip":
                await websocket.send_json({"status": "extrayendo", "mensaje": "Descomprimiendo y limpiando..."})
                try:
                    with zipfile.ZipFile(ruta_temp, 'r') as z:
                        nombres = z.namelist()
                        z.extractall(ruta_base)
                        
                        if nombres:
                            archivo_elegido = nombres[0]
                            ruta_final = str(ruta_base / archivo_elegido)
                            
                            for archivo in nombres[1:]:
                                ruta_sobrante = ruta_base / archivo
                                if ruta_sobrante.exists():
                                    ruta_sobrante.unlink() 
                        else:
                            await websocket.send_json({"status": "error", "mensaje": "ZIP vacío"})
                            return
                            
                    ruta_temp.unlink()
                except Exception as e:
                    await websocket.send_json({"status": "error", "mensaje": f"Error: {str(e)}"})
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
                "mensaje": "Juego listo en tu biblioteca.",
                "ruta_rom": str(ruta_final)
            })

        except WebSocketDisconnect:
            print("Cliente desconectado.")
        except Exception as e:
            await websocket.send_json({"status": "error", "mensaje": f"Error crítico: {str(e)}"})
        finally:
            await websocket.close()
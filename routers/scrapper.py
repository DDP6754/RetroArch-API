import zipfile
import httpx
from pathlib import Path
from urllib.parse import unquote
from sqlalchemy.future import select
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, Depends
from database import AsyncSessionLocal, Juego, Consola
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

router = APIRouter(tags=["Scrapper"])

SISTEMAS_URLS = {
    "gba": "https://archive.org/download/GameboyAdvanceRomCollectionByGhostware/",
    "ds": "https://archive.org/download/nds_apfix/apfix/",
    "gamecube": "https://archive.org/download/gamecubecollectionbyblopez/"
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

@router.get("/scrapper/buscar")
async def buscar_juegos_global(
    search: str = Query("", description="Buscar juego por nombre"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    """
    Busca un juego en todos los sistemas y devuelve resultados paginados.
    """
    resultados_globales = []
    exts = [".zip", ".nds", ".gba", ".rvz", ".iso", ".sfc", ".nes"]
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        for sistema, url_base in SISTEMAS_URLS.items():
            try:
                response = await client.get(url_base, headers=HEADERS)
                if response.status_code != 200: continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if href and any(href.lower().endswith(e) for e in exts) and not href.startswith(('?', '/')):
                        nombre_limpio = unquote(href).rsplit('.', 1)[0]
                        
                        if (search or "").lower() in nombre_limpio.lower():
                            resultados_globales.append({
                                "nombre": nombre_limpio,
                                "url_descarga": f"{url_base}{href}",
                                "consola": sistema
                            })
            except Exception as e:
                print(f"Error en {sistema}: {e}")
                continue

    total = len(resultados_globales)
    start = (page - 1) * size
    end = start + size
    
    juegos_paginados = resultados_globales[start:end]

    return {
        "busqueda": search,
        "total_resultados": total,
        "pagina_actual": page,
        "tamaño_pagina": size,
        "total_paginas": (total + size - 1) // size,
        "juegos": juegos_paginados
    }

@router.websocket("/ws/descargar/{consola_nombre}")
async def websocket_descargar(
    websocket: WebSocket, 
    consola: str, 
    db: AsyncSession = Depends(get_db),
    p_access_token_id: Optional[str] = Query(None, alias="P-Access-Token-Id"),
    p_access_token: Optional[str] = Query(None, alias="P-Access-Token")
):
    """WebSocket que evita descargas duplicadas usando el nombre del archivo original."""
    await websocket.accept()
    
    async with AsyncSessionLocal() as db:
        try:
            data = await websocket.receive_json()
            url_descarga = data.get("url")
            nombre_juego = data.get("nombre")
            perfil_id = data.get("perfil_id")
            nombre_archivo_real = url_descarga.split('/')[-1]

            res_existencia = await db.execute(
                select(Juego).where(
                    Juego.archivo_origen == nombre_archivo_real,
                    Juego.perfil_id == perfil_id
                )
            )
            if res_existencia.scalars().first():
                await websocket.send_json({
                    "status": "error", 
                    "mensaje": "Este juego ya está en tu biblioteca (archivo duplicado)."
                })
                await websocket.close()
                return

            res_c = await db.execute(select(Consola).where(Consola.console == consola_nombre.lower()))
            consola = res_c.scalars().first()
            if not consola:
                await websocket.send_json({"status": "error", "mensaje": f"Consola '{consola_nombre}' no existe."})
                await websocket.close()
                return

            ruta_base = Path(f"./storage/roms/{consola_nombre}")
            ruta_base.mkdir(parents=True, exist_ok=True)
            
            ext = nombre_archivo_real.split('.')[-1].lower()
            nombre_seguro = "".join(c for c in nombre_juego if c.isalnum() or c in (' ', '_', '-')).strip()
            ruta_temp = ruta_base / f"{nombre_seguro}.{ext}"
            
            ruta_final = None

            async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                async with client.stream("GET", url_descarga, headers=HEADERS) as r:
                    if r.status_code != 200:
                        await websocket.send_json({"status": "error", "mensaje": "Error de conexión con Archive.org."})
                        return
                    
                    total_bytes = int(r.headers.get("Content-Length", 0))
                    descargado_bytes = 0
                    
                    with open(ruta_temp, "wb") as f:
                        async for chunk in r.aiter_bytes(chunk_size=131072): # 128KB
                            f.write(chunk)
                            descargado_bytes += len(chunk)
                            
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
                await websocket.send_json({"status": "extrayendo", "mensaje": "Descomprimiendo contenido..."})
                try:
                    with zipfile.ZipFile(ruta_temp, 'r') as z:
                        nombres = z.namelist()
                        z.extractall(ruta_base)
                        
                        if nombres:
                            archivo_elegido = nombres[0]
                            ruta_final = str(ruta_base / archivo_elegido)
                            
                            for archivo in nombres[1:]:
                                (ruta_base / archivo).unlink(missing_ok=True)
                        
                    ruta_temp.unlink()
                except Exception as e:
                    await websocket.send_json({"status": "error", "mensaje": f"Error al extraer: {str(e)}"})
                    return

            nuevo_registro = Juego(
                juego=nombre_juego,
                archivo_origen=nombre_archivo_real,
                ruta_rom=str(ruta_final),
                consola_id=consola.id,
                perfil_id=perfil_id
            )
            
            db.add(nuevo_registro)
            await db.commit()
            
            await websocket.send_json({
                "status": "completado", 
                "mensaje": "Juego guardado correctamente.",
                "ruta_rom": str(ruta_final)
            })

        except WebSocketDisconnect:
            print(f"Descarga cancelada: El usuario cerró la conexión.")
        except Exception as e:
            await websocket.send_json({"status": "error", "mensaje": f"Error crítico: {str(e)}"})
        finally:
            try:
                await websocket.close()
            except:
                pass

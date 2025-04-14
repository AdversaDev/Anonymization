from typing import Any, Dict, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, RedirectResponse
import os
import io
import re
import json
import uuid
import hashlib
import traceback
import asyncio
import requests
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Union
import logging
import time
import psycopg2
from app.queue_manager import queue_manager
from typing import Optional, Dict, Any, Union, List, Tuple

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

ANONYMIZATION_URL = "http://anonymization_service:8001"

# Słownik przechowujący mapowanie między skrótami zawartości a session_id
# Klucz: hash zawartości, Wartość: session_id
content_session_mapping: Dict[str, str] = {}

# Konfiguracja bazy danych
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anon_user:securepassword@db/anon_db")

def get_db_connection():
    """Nawiązuje połączenie z bazą danych."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Błąd połączenia z bazą danych: {str(e)}")
        raise

async def check_session_id_exists(session_id: str) -> bool:
    """
    Sprawdza, czy session_id istnieje w bazie danych i czy zawiera mapowania.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM anonymization WHERE session_id = %s",
            (session_id,)
        )
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count > 0
    except Exception as e:
        logger.error(f"Błąd podczas sprawdzania session_id: {str(e)}")
        return False

@router.post("/anonymize")
def anonymize(data: dict) -> Dict[str, Any]:
    # Generieren einer eindeutigen Session-ID, wenn keine vorhanden ist
    if "session_id" not in data:
        data["session_id"] = str(uuid.uuid4())
    
    # Wenn nur Text übergeben wird, entsprechend verarbeiten
    if "text" in data and isinstance(data["text"], str):
        text = data["text"]
        session_id = data["session_id"]
        
        try:
            anonymized_text = anonymize_text_via_api(text, session_id)
            return {
                "session_id": session_id,
                "anonymized_text": anonymized_text
            }
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Fehler bei der Anonymisierung: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Fehler bei der Anonymisierung: {str(e)}")
    
    # Standardverhalten für andere Datentypen
    response = requests.post(f"{ANONYMIZATION_URL}/anonymize", json=data)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Fehler bei der Kommunikation mit dem Anonymisierungsdienst")
    
    result = response.json()
    # Stellen Sie sicher, dass die Session-ID immer zurückgegeben wird
    if "session_id" not in result and "session_id" in data:
        result["session_id"] = data["session_id"]
        
    return result




@router.post("/deanonymize")
def deanonymize(data: dict) -> Dict[str, Any]:
    """Endpunkt zur Wiederherstellung der Originaldaten basierend auf der Session-ID."""
    logger.info(f"Otrzymano żądanie deanonimizacji: {data}")
    session_id = data.get("session_id", "")
    text = data.get("text", "")
    
    logger.info(f"Deanonimizacja - session_id: {session_id}, długość tekstu: {len(text)}")
    
    if not session_id or not text:
        logger.error(f"Brak wymaganych danych: session_id={bool(session_id)}, text={bool(text)}")
        raise HTTPException(status_code=400, detail="Session-ID und Text sind erforderlich")
    
    # Sprawdzamy, czy session_id istnieje w bazie danych
    session_exists = asyncio.run(check_session_id_exists(session_id))
    if not session_exists:
        logger.warning(f"Session_id {session_id} nie istnieje w bazie danych lub nie zawiera mapowań")
        # Dodajemy informację dla użytkownika, ale nie rzucamy wyjątku
    
    try:
        # Direkter Aufruf der deanonymize_text_via_api-Funktion für bessere Fehlerbehandlung
        logger.info(f"Wywołanie deanonymize_text_via_api z session_id: {session_id}")
        deanonymized_text = deanonymize_text_via_api(text, session_id)
        logger.info(f"Otrzymano zdeanonimizowany tekst o długości: {len(deanonymized_text)}")
        return {
            "session_id": session_id,
            "deanonymized_text": deanonymized_text
        }
    except HTTPException as e:
        logger.error(f"HTTPException w deanonymize: {e.detail}, status_code: {e.status_code}")
        raise e
    except Exception as e:
        logger.error(f"Fehler bei der Deanonymisierung: {str(e)}")
        logger.error(f"Szczegóły błędu: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Fehler bei der Deanonymisierung: {str(e)}")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Obsługuje przesyłanie plików do anonimizacji z unikalnym session_id.
    Dodaje plik do kolejki przetwarzania i przekierowuje na stronę potwierdzenia.
    """
    try:
        # Generujemy unikalny identyfikator dla pliku i sesji
        file_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        # Odczytujemy zawartość pliku
        content = await file.read()
        filename = file.filename.lower() if file.filename else ""
        file_size = len(content)
        
        logger.info(f"Dodawanie pliku {filename} (rozmiar: {file_size} bajtów) do kolejki, ID: {file_id}")
        
        # Zapisujemy metadane pliku
        file_metadata = {
            "file_id": file_id,
            "session_id": session_id,
            "filename": filename,
            "original_name": file.filename,
            "content_type": file.content_type,
            "size": file_size,
            "status": "queued",
            "queued_at": time.time()
        }
        
        # Definiujemy funkcję asynchroniczną do przetwarzania pliku
        async def process_file(file_id: str):
            try:
                logger.info(f"Rozpoczęcie przetwarzania pliku {file_id}")
                
                if filename.endswith((".json", ".fhir")):
                    # Pliki JSON i FHIR
                    data = json.loads(content.decode("utf-8"))
                    
                    # Zapisujemy mapowanie oryginalnej zawartości do session_id
                    store_content_session_mapping(data, session_id)
                    
                    processed_data = process_json(data, session_id)
                    
                    # Zapisujemy mapowanie przetworzonej zawartości do session_id
                    store_content_session_mapping(processed_data, session_id)
                    
                    if isinstance(processed_data, dict):
                        processed_data["session_id"] = session_id
                    file_content = json.dumps(processed_data, ensure_ascii=False, indent=2)
                    file_bytes = io.BytesIO(file_content.encode("utf-8"))
                    headers = {"Content-Disposition": f"attachment; filename={session_id}.json"}
                    return {
                        "content": file_bytes.getvalue(),
                        "media_type": "application/json",
                        "headers": headers,
                        "filename": f"{session_id}.json"
                    }
                
                elif filename.endswith(".xml"):
                    # Pliki XML
                    root = ET.fromstring(content)
                    
                    # Zapisujemy mapowanie oryginalnej zawartości do session_id
                    original_xml = ET.tostring(root, encoding='unicode', method='xml')
                    store_content_session_mapping(original_xml, session_id)
                    
                    process_xml(root, session_id)
                    root.insert(0, ET.Element("session_id"))
                    root[0].text = session_id
                    final_xml = ET.tostring(root, encoding='unicode', method='xml')
                    
                    # Zapisujemy mapowanie przetworzonej zawartości do session_id
                    store_content_session_mapping(final_xml, session_id)
                    
                    file_bytes = io.BytesIO(final_xml.encode("utf-8"))
                    headers = {"Content-Disposition": f"attachment; filename={session_id}.xml"}
                    return {
                        "content": file_bytes.getvalue(),
                        "media_type": "application/xml",
                        "headers": headers,
                        "filename": f"{session_id}.xml"
                    }
                
                elif filename.endswith(".txt"):
                    # Pliki tekstowe
                    text = content.decode("utf-8")
                    
                    # Zapisujemy mapowanie oryginalnej zawartości do session_id
                    store_content_session_mapping(text, session_id)
                    
                    processed_text = anonymize_text_via_api(text, session_id)
                    
                    # Zapisujemy mapowanie przetworzonej zawartości do session_id
                    store_content_session_mapping(processed_text, session_id)
                    
                    final_text = f"SessionID: {session_id}\n" + processed_text
                    file_bytes = io.BytesIO(final_text.encode("utf-8"))
                    headers = {"Content-Disposition": f"attachment; filename={session_id}.txt"}
                    return {
                        "content": file_bytes.getvalue(),
                        "media_type": "text/plain",
                        "headers": headers,
                        "filename": f"{session_id}.txt"
                    }
                
                else:
                    raise ValueError(f"Nieobsługiwany format pliku: {filename}")
                    
            except Exception as e:
                logger.error(f"Błąd podczas przetwarzania pliku {file_id}: {str(e)}")
                return {"error": str(e)}
        
        # Dodajemy plik do kolejki przetwarzania
        await queue_manager.add_to_queue(file_id, process_file)
        
        # Przekierowujemy na stronę potwierdzenia z parametrami
        return RedirectResponse(
            url=f"/upload-confirmation?file_id={file_id}&session_id={session_id}",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Błąd podczas dodawania pliku do kolejki: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Błąd przetwarzania pliku: {str(e)}")


@router.get("/status/{file_id}", response_class=HTMLResponse)
async def check_status_html(file_id: str):
    """
    Wyświetla stronę HTML ze statusem przetwarzania pliku.
    """
    try:
        # Pobieramy status pliku z kolejki
        file_status = await queue_manager.get_status(file_id)
        
        # Jeśli plik nie został znaleziony w kolejce, spróbujmy pobrać jego wynik
        if not file_status:
            # Spróbujmy pobrać wynik bez czekania (timeout=0)
            result = await queue_manager.get_result(file_id, timeout=0)
            
            if result:
                # Jeśli mamy wynik, to plik został już przetworzony
                file_status = {
                    "status": "completed",
                    "result": result
                }
            else:
                # Plik nie został znaleziony ani w kolejce, ani w wynikach
                html_content = f"""
                <html>
                  <head>
                    <title>Status - Anonymisierungsdienst</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <style>
                      body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                      h1 {{ color: #2c3e50; }}
                      h2 {{ color: #3498db; margin-top: 20px; }}
                      .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                      .error-box {{ background-color: #f8d7da; padding: 20px; border-radius: 5px; margin-top: 20px; }}
                      .error {{ color: #dc3545; }}
                      .home-link {{ margin-top: 30px; display: block; }}
                    </style>
                  </head>
                  <body>
                    <div class="container">
                      <h1>Anonymisierungsdienst</h1>
                      
                      <div class="error-box">
                        <h2 class="error">Datei nicht gefunden</h2>
                        <p>Die angegebene Datei-ID wurde nicht gefunden: {file_id}</p>
                      </div>
                      
                      <a href="/" class="home-link">Zurück zur Startseite</a>
                    </div>
                  </body>
                </html>
                """
                return HTMLResponse(content=html_content, status_code=404)
        
        # Jeśli mamy status pliku, kontynuujemy
        status = file_status.get("status", "unknown")
        status_translation = {
            "queued": "In Warteschlange",
            "processing": "Wird verarbeitet",
            "completed": "Abgeschlossen",
            "error": "Fehler"
        }.get(status, status)
        
        html_content = f"""
        <html>
          <head>
            <title>Status - Anonymisierungsdienst</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
              body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
              h1 {{ color: #2c3e50; }}
              h2 {{ color: #3498db; margin-top: 20px; }}
              .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
              .info-box {{ background-color: #e8f4f8; padding: 20px; border-radius: 5px; margin-top: 20px; }}
              .success {{ color: #27ae60; }}
              .warning {{ color: #f39c12; }}
              .error {{ color: #e74c3c; }}
              .id-box {{ background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin: 10px 0; font-family: monospace; font-size: 16px; }}
              .button-container {{ margin-top: 20px; }}
              .button {{ display: inline-block; background-color: #3498db; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; margin-right: 10px; }}
              .button:hover {{ background-color: #2980b9; }}
              .home-link {{ margin-top: 30px; display: block; }}
              .status-info {{ margin-top: 15px; }}
              .refresh-button {{ margin-top: 20px; }}
            </style>
          </head>
          <body>
            <div class="container">
              <h1>Anonymisierungsdienst</h1>
              
              <div class="info-box">
                <h2>Status der Datei</h2>
                <p><strong>Datei-ID:</strong> <span class="id-box">{file_id}</span></p>
        """
        
        # Dodajemy informacje o statusie w zależności od stanu pliku
        if status == "queued":
            position = file_status.get("position", 0)
            estimated_wait_time = file_status.get("estimated_wait_time", 0)
            html_content += f"""
                <div class="status-info warning">
                  <h3>Status: {status_translation}</h3>
                  <p>Position in der Warteschlange: {position}</p>
                  <p>Geschätzte Wartezeit: {round(estimated_wait_time)} Sekunden</p>
                </div>
                <button class="refresh-button" onclick="location.reload()">Status aktualisieren</button>
            """
        elif status == "processing":
            processing_time = file_status.get("processing_time", 0)
            html_content += f"""
                <div class="status-info warning">
                  <h3>Status: {status_translation}</h3>
                  <p>Verarbeitungszeit: {processing_time:.2f} Sekunden</p>
                </div>
                <button class="refresh-button" onclick="location.reload()">Status aktualisieren</button>
            """
        elif status == "completed":
            html_content += f"""
                <div class="status-info success">
                  <h3>Status: {status_translation}</h3>
                  <p>Die Datei wurde erfolgreich verarbeitet und ist bereit zum Herunterladen.</p>
                </div>
                <div class="button-container">
                  <a href="/download/{file_id}" class="button">Datei herunterladen</a>
                </div>
            """
        elif status == "error":
            error_message = file_status.get("error", "Unbekannter Fehler")
            html_content += f"""
                <div class="status-info error">
                  <h3>Status: {status_translation}</h3>
                  <p>Bei der Verarbeitung der Datei ist ein Fehler aufgetreten:</p>
                  <p>{error_message}</p>
                </div>
            """
        else:
            html_content += f"""
                <div class="status-info">
                  <h3>Status: {status_translation}</h3>
                  <p>Unbekannter Status</p>
                </div>
            """
        
        html_content += f"""
              </div>
              
              <a href="/" class="home-link">Zurück zur Startseite</a>
            </div>
          </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Błąd podczas sprawdzania statusu pliku {file_id}: {str(e)}")
        html_content = f"""
        <html>
          <head>
            <title>Fehler - Anonymisierungsdienst</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
              body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
              h1 {{ color: #2c3e50; }}
              h2 {{ color: #3498db; margin-top: 20px; }}
              .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
              .error-box {{ background-color: #f8d7da; padding: 20px; border-radius: 5px; margin-top: 20px; }}
              .error {{ color: #dc3545; }}
              .home-link {{ margin-top: 30px; display: block; }}
            </style>
          </head>
          <body>
            <div class="container">
              <h1>Anonymisierungsdienst</h1>
              
              <div class="error-box">
                <h2 class="error">Fehler beim Prüfen des Status</h2>
                <p>{str(e)}</p>
              </div>
              
              <a href="/" class="home-link">Zurück zur Startseite</a>
            </div>
          </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=500)

@router.get("/api/status/{file_id}")
async def check_status(file_id: str):
    """
    Sprawdza status przetwarzania pliku w kolejce.
    Zwraca informacje o statusie pliku i szacowany czas oczekiwania.
    """
    try:
        # Sprawdzamy pozycję w kolejce
        position = await queue_manager._get_queue_position(file_id)
        
        if position is not None:
            # Plik jest w kolejce
            return {
                "file_id": file_id,
                "status": "queued",
                "position": position,
                "estimated_wait_time": position * 60  # Szacujemy 60 sekund na plik
            }
        elif file_id == queue_manager._current_file_id:
            # Plik jest aktualnie przetwarzany
            processing_time = time.time() - queue_manager._start_time if queue_manager._start_time else 0
            return {
                "file_id": file_id,
                "status": "processing",
                "processing_time": f"{processing_time:.2f} sekund"
            }
        elif file_id in queue_manager._results:
            # Plik został już przetworzony
            return {
                "file_id": file_id,
                "status": "completed",
                "download_url": f"/download/{file_id}"
            }
        else:
            # Nie znaleziono pliku
            raise HTTPException(status_code=404, detail=f"Nie znaleziono pliku o ID: {file_id}")
    except Exception as e:
        logger.error(f"Błąd podczas sprawdzania statusu pliku {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{file_id}")
async def download_file(file_id: str):
    """
    Pobiera przetworzony plik z kolejki.
    Jeśli plik nie został jeszcze przetworzony, zwraca błąd 404.
    """
    try:
        # Sprawdzamy, czy plik został już przetworzony
        result = await queue_manager.get_result(file_id, timeout=1)  # Krótki timeout, bo tylko sprawdzamy
        
        if result is None:
            # Plik jeszcze nie został przetworzony lub nie istnieje
            status = await check_status(file_id)
            if status["status"] == "queued":
                return {
                    "file_id": file_id,
                    "status": "queued",
                    "message": "Plik jest w kolejce, proszę sprawdzić później",
                    "position": status["position"],
                    "estimated_wait_time": status["estimated_wait_time"]
                }
            elif status["status"] == "processing":
                return {
                    "file_id": file_id,
                    "status": "processing",
                    "message": "Plik jest przetwarzany, proszę sprawdzić później",
                    "processing_time": status["processing_time"]
                }
            else:
                raise HTTPException(status_code=404, detail=f"Nie znaleziono pliku o ID: {file_id}")
        
        # Sprawdzamy, czy wystąpił błąd podczas przetwarzania
        if "error" in result:
            raise HTTPException(status_code=500, detail=f"Błąd podczas przetwarzania pliku: {result['error']}")
        
        # Zwracamy przetworzony plik
        content = result["content"]
        media_type = result["media_type"]
        headers = result["headers"]
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas pobierania pliku {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upload-confirmation")
async def upload_confirmation(file_id: str, session_id: str):
    """
    Wyświetla stronę potwierdzenia po przesłaniu pliku.
    Zawiera ID pliku, ID sesji oraz przyciski do sprawdzenia statusu i pobrania pliku.
    """
    html_content = f"""
    <html>
      <head>
        <title>Datei hochgeladen - Anonymisierungsdienst</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
          h1 {{ color: #2c3e50; }}
          h2 {{ color: #3498db; margin-top: 20px; }}
          .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
          .info-box {{ background-color: #e8f4f8; padding: 20px; border-radius: 5px; margin-top: 20px; }}
          .success {{ color: #27ae60; }}
          .id-box {{ background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin: 10px 0; font-family: monospace; font-size: 16px; }}
          .button-container {{ margin-top: 20px; }}
          .button {{ display: inline-block; background-color: #3498db; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; margin-right: 10px; }}
          .button:hover {{ background-color: #2980b9; }}
          .home-link {{ margin-top: 30px; display: block; }}
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Anonymisierungsdienst</h1>
          
          <div class="info-box">
            <h2 class="success">Datei erfolgreich hochgeladen!</h2>
            <p>Ihre Datei wurde erfolgreich hochgeladen und zur Verarbeitung in die Warteschlange gestellt.</p>
            
            <h3>Datei-ID:</h3>
            <div class="id-box" id="file-id">{file_id}</div>
            <button onclick="copyToClipboard('file-id')">ID kopieren</button>
            
            <h3>Session-ID:</h3>
            <div class="id-box" id="session-id">{session_id}</div>
            <button onclick="copyToClipboard('session-id')">ID kopieren</button>
            
            <p>Bitte bewahren Sie diese IDs auf, um den Status Ihrer Datei zu überprüfen und die anonymisierte Datei herunterzuladen.</p>
            
            <div class="button-container">
              <a href="/status/{file_id}" class="button">Status prüfen</a>
              <a href="/download/{file_id}" class="button">Datei herunterladen</a>
            </div>
          </div>
          
          <a href="/" class="home-link">Zurück zur Startseite</a>
        </div>
        
        <script>
          function copyToClipboard(elementId) {{
            const text = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(text).then(() => {{
              alert('In die Zwischenablage kopiert!');
            }}).catch(err => {{
              console.error('Fehler beim Kopieren:', err);
              alert('Fehler beim Kopieren in die Zwischenablage');
            }});
          }}
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/upload-deanonymize")
async def upload_deanonymize_file(
    file: UploadFile = File(...), 
    session_id: str = Form(None)
) -> StreamingResponse:
    """
    Obsługuje przesyłanie plików do deanonimizacji.
    System automatycznie wykrywa session_id na podstawie:
    1. Parametru formularza session_id (jeśli podany)
    2. Nazwy pliku (jeśli zawiera UUID)
    3. Zawartości pliku (jeśli zawiera session_id)
    Wynik jest zwracany jako plik do pobrania.
    """
    try:
        content = await file.read()
        filename = file.filename.lower() if file.filename else ""
        
        # Próba automatycznego wykrycia session_id
        detected_session_id = None
        
        # 1. Sprawdź, czy session_id został podany jako parametr formularza
        if session_id:
            detected_session_id = session_id
            logger.info(f"Używam session_id z formularza: {detected_session_id}")
        
        # 2. Sprawdź, czy nazwa pliku zawiera UUID, który może być session_id
        if not detected_session_id and filename:
            # Wyodrębniamy część nazwy pliku przed rozszerzeniem
            base_name = os.path.splitext(filename)[0]
            # Sprawdź, czy nazwa pliku pasuje do wzorca UUID
            uuid_pattern = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', re.IGNORECASE)
            uuid_match = uuid_pattern.search(base_name)
            
            if uuid_match:
                detected_session_id = uuid_match.group(0)
                logger.info(f"Wykryto session_id z nazwy pliku: {detected_session_id}")
        
        # Przetwarzanie plików JSON/FHIR
        if filename.endswith((".json", ".fhir")):
            data = json.loads(content.decode("utf-8"))
            
            # 3. Sprawdź, czy plik JSON zawiera session_id
            if not detected_session_id and "session_id" in data:
                detected_session_id = data["session_id"]
                del data["session_id"]
                logger.info(f"Używam session_id z pliku JSON: {detected_session_id}")
            
            # Jeśli nadal nie mamy session_id, sprawdźmy w bazie danych
            if not detected_session_id:
                # Próba znalezienia session_id w bazie danych na podstawie zawartości
                detected_session_id = await find_session_id_for_content(data)
                if detected_session_id:
                    logger.info(f"Znaleziono session_id w bazie danych: {detected_session_id}")
            
            if not detected_session_id:
                raise HTTPException(status_code=400, detail="Nie można automatycznie wykryć session_id. Podaj session_id jako parametr formularza.")
            
            # Zamiast konwertować cały plik JSON do tekstu, wyodrębnimy wszystkie tokeny i zdeanonimizujemy je pojedynczo
            logger.info(f"Wyodrębnianie tokenów z pliku JSON z session_id: {detected_session_id}")
            
            # Konwertujemy dane JSON do tekstu
            json_text = json.dumps(data, ensure_ascii=False)
            
            # Wyodrębniamy wszystkie tokeny anno_XXXXXXXX
            anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
            anno_tokens = anno_pattern.findall(json_text)
            unique_tokens = sorted(set(anno_tokens))
            
            logger.info(f"Znaleziono {len(unique_tokens)} unikalnych tokenów w pliku JSON")
            
            # Jeśli nie ma tokenów do deanonimizacji, zwracamy oryginalne dane
            if not unique_tokens:
                logger.info("Brak tokenów do deanonimizacji w pliku JSON")
                processed_data = data
                if "session_id" not in processed_data and detected_session_id:
                    processed_data["session_id"] = detected_session_id
            else:
                # Deanonimizujemy każdy token osobno
                token_mapping = {}
                for token in unique_tokens:
                    # Przygotowanie danych do deanonimizacji pojedynczego tokenu
                    payload = {
                        "session_id": detected_session_id,
                        "text": token
                    }
                    
                    # Wywołujemy deanonimizację dla pojedynczego tokenu
                    logger.info(f"Deanonimizacja tokenu: {token}")
                    response = requests.post(f"http://anonymization:8001/deanonymize", json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        deanonymized_token = result.get("deanonymized_text")
                        
                        if deanonymized_token and deanonymized_token != token:
                            # Jeśli token został zdeanonimizowany, dodajemy go do mapowania
                            token_mapping[token] = deanonymized_token
                            logger.info(f"Token {token} zdeanonimizowany do: {deanonymized_token}")
                        else:
                            # Jeśli token nie został zdeanonimizowany, zostawiamy go bez zmian
                            token_mapping[token] = token
                            logger.info(f"Token {token} nie został zdeanonimizowany")
                    else:
                        # W przypadku błędu, zostawiamy token bez zmian
                        token_mapping[token] = token
                        logger.error(f"Błąd podczas deanonimizacji tokenu {token}: {response.status_code}, {response.text}")
                
                # Zastepujemy wszystkie tokeny w tekście
                deanonymized_text = json_text
                for token, original in token_mapping.items():
                    # Upewniamy się, że zastępujemy tylko całe tokeny, a nie części innych tokenów
                    pattern = r'\b' + re.escape(token) + r'\b'
                    deanonymized_text = re.sub(pattern, original, deanonymized_text)
                
                # Konwertujemy zdeanonimizowany tekst z powrotem do JSON
                try:
                    processed_data = json.loads(deanonymized_text)
                    # Dodajemy z powrotem session_id, jeśli był usunięty
                    if "session_id" not in processed_data and detected_session_id:
                        processed_data["session_id"] = detected_session_id
                except json.JSONDecodeError as e:
                    # Jeśli nie możemy skonwertować do JSON, zwracamy tekst jako jest
                    logger.error(f"Błąd podczas konwersji zdeanonimizowanego tekstu do JSON: {str(e)}")
                    processed_data = {"deanonymized_text": deanonymized_text, "session_id": detected_session_id}
            
            file_content = json.dumps(processed_data, ensure_ascii=False, indent=2)
            file_bytes = io.BytesIO(file_content.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={detected_session_id}_deanon.json"}
            return StreamingResponse(file_bytes, media_type="application/json", headers=headers)
        
        # Przetwarzanie plików XML
        elif filename.endswith(".xml"):
            root = ET.fromstring(content)
            
            # 3. Sprawdź, czy plik XML zawiera session_id
            if not detected_session_id and len(root) > 0 and root[0].tag == "session_id":
                detected_session_id = root[0].text
                if detected_session_id:
                    root.remove(root[0])
                    logger.info(f"Używam session_id z pliku XML: {detected_session_id}")
            
            # Jeśli nadal nie mamy session_id, sprawdźmy w bazie danych
            if not detected_session_id:
                # Próba znalezienia session_id w bazie danych na podstawie zawartości
                xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
                detected_session_id = await find_session_id_for_content(xml_str)
                if detected_session_id:
                    logger.info(f"Znaleziono session_id w bazie danych: {detected_session_id}")
            
            if not detected_session_id:
                raise HTTPException(status_code=400, detail="Nie można automatycznie wykryć session_id. Podaj session_id jako parametr formularza.")
                
            # Konwertujemy XML do tekstu
            xml_text = ET.tostring(root, encoding='unicode', method='xml')
            
            # Wyodrębniamy wszystkie tokeny anno_XXXXXXXX
            anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
            anno_tokens = anno_pattern.findall(xml_text)
            unique_tokens = sorted(set(anno_tokens))
            
            logger.info(f"Znaleziono {len(unique_tokens)} unikalnych tokenów w pliku XML")
            
            # Jeśli nie ma tokenów do deanonimizacji, zwracamy oryginalny XML
            if not unique_tokens:
                logger.info("Brak tokenów do deanonimizacji w pliku XML")
                processed_xml = xml_text
            else:
                # Deanonimizujemy każdy token osobno
                token_mapping = {}
                for token in unique_tokens:
                    # Przygotowanie danych do deanonimizacji pojedynczego tokenu
                    payload = {
                        "session_id": detected_session_id,
                        "text": token
                    }
                    
                    # Wywołujemy deanonimizację dla pojedynczego tokenu
                    logger.info(f"Deanonimizacja tokenu: {token}")
                    response = requests.post(f"http://anonymization:8001/deanonymize", json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        deanonymized_token = result.get("deanonymized_text")
                        
                        if deanonymized_token and deanonymized_token != token:
                            # Jeśli token został zdeanonimizowany, dodajemy go do mapowania
                            token_mapping[token] = deanonymized_token
                            logger.info(f"Token {token} zdeanonimizowany do: {deanonymized_token}")
                        else:
                            # Jeśli token nie został zdeanonimizowany, zostawiamy go bez zmian
                            token_mapping[token] = token
                            logger.info(f"Token {token} nie został zdeanonimizowany")
                    else:
                        # W przypadku błędu, zostawiamy token bez zmian
                        token_mapping[token] = token
                        logger.error(f"Błąd podczas deanonimizacji tokenu {token}: {response.status_code}, {response.text}")
                
                # Zastepujemy wszystkie tokeny w tekście
                processed_xml = xml_text
                for token, original in token_mapping.items():
                    # Upewniamy się, że zastępujemy tylko całe tokeny, a nie części innych tokenów
                    pattern = r'\b' + re.escape(token) + r'\b'
                    processed_xml = re.sub(pattern, original, processed_xml)
            
            file_bytes = io.BytesIO(processed_xml.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={detected_session_id}_deanon.xml"}
            return StreamingResponse(file_bytes, media_type="application/xml", headers=headers)
        
        # Przetwarzanie plików TXT
        elif filename.endswith(".txt"):
            text = content.decode("utf-8")
            text_to_process = text
            
            # 3. Sprawdź, czy plik TXT zawiera session_id
            if not detected_session_id:
                lines = text.splitlines()
                if lines and lines[0].startswith("SessionID:"):
                    detected_session_id = lines[0].split("SessionID:")[1].strip()
                    text_to_process = "\n".join(lines[1:])  # usuń linię z sessionID
                    logger.info(f"Używam session_id z pliku TXT: {detected_session_id}")
            
            # Jeśli nadal nie mamy session_id, sprawdźmy w bazie danych
            if not detected_session_id:
                # Próba znalezienia session_id w bazie danych na podstawie zawartości
                detected_session_id = await find_session_id_for_content(text_to_process)
                if detected_session_id:
                    logger.info(f"Znaleziono session_id w bazie danych: {detected_session_id}")
            
            if not detected_session_id:
                raise HTTPException(status_code=400, detail="Nie można automatycznie wykryć session_id. Podaj session_id jako parametr formularza.")
            
            # Wyodrębniamy wszystkie tokeny anno_XXXXXXXX
            anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
            anno_tokens = anno_pattern.findall(text_to_process)
            unique_tokens = sorted(set(anno_tokens))
            
            logger.info(f"Znaleziono {len(unique_tokens)} unikalnych tokenów w pliku TXT")
            
            # Jeśli nie ma tokenów do deanonimizacji, zwracamy oryginalny tekst
            if not unique_tokens:
                logger.info("Brak tokenów do deanonimizacji w pliku TXT")
                processed_text = text_to_process
            else:
                # Deanonimizujemy każdy token osobno
                token_mapping = {}
                for token in unique_tokens:
                    # Przygotowanie danych do deanonimizacji pojedynczego tokenu
                    payload = {
                        "session_id": detected_session_id,
                        "text": token
                    }
                    
                    # Wywołujemy deanonimizację dla pojedynczego tokenu
                    logger.info(f"Deanonimizacja tokenu: {token}")
                    response = requests.post(f"http://anonymization:8001/deanonymize", json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        deanonymized_token = result.get("deanonymized_text")
                        
                        if deanonymized_token and deanonymized_token != token:
                            # Jeśli token został zdeanonimizowany, dodajemy go do mapowania
                            token_mapping[token] = deanonymized_token
                            logger.info(f"Token {token} zdeanonimizowany do: {deanonymized_token}")
                        else:
                            # Jeśli token nie został zdeanonimizowany, zostawiamy go bez zmian
                            token_mapping[token] = token
                            logger.info(f"Token {token} nie został zdeanonimizowany")
                    else:
                        # W przypadku błędu, zostawiamy token bez zmian
                        token_mapping[token] = token
                        logger.error(f"Błąd podczas deanonimizacji tokenu {token}: {response.status_code}, {response.text}")
                
                # Zastepujemy wszystkie tokeny w tekście
                processed_text = text_to_process
                for token, original in token_mapping.items():
                    # Upewniamy się, że zastępujemy tylko całe tokeny, a nie części innych tokenów
                    pattern = r'\b' + re.escape(token) + r'\b'
                    processed_text = re.sub(pattern, original, processed_text)
            
            file_bytes = io.BytesIO(processed_text.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={detected_session_id}_deanon.txt"}
            return StreamingResponse(file_bytes, media_type="text/plain", headers=headers)
        
        else:
            raise HTTPException(status_code=415, detail="Unsupported file format")
    
    except Exception as e:
        logger.error(f"Błąd podczas przetwarzania pliku: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


# Rekurencyjne przetwarzanie JSON do anonimizacji
def anonymize_text_in_json(data: Any, session_id: str) -> Any:
    if isinstance(data, dict):
        return {key: anonymize_text_in_json(value, session_id) for key, value in data.items()}
    elif isinstance(data, list):
        return [anonymize_text_in_json(item, session_id) for item in data]
    elif isinstance(data, str):
        return anonymize_text_via_api(data, session_id)
    else:
        return data


def process_json(data: dict, session_id: str) -> Any:
    """Anonimizacja danych w formacie JSON (np. FHIR)."""
    return anonymize_text_in_json(data, session_id)


# Funkcja do znajdowania session_id na podstawie zawartości
async def find_session_id_for_content(content: Union[str, dict, list]) -> Optional[str]:
    """
    Próbuje znaleźć session_id na podstawie zawartości pliku.
    
    Strategia:
    1. Oblicza hash zawartości
    2. Sprawdza, czy hash istnieje w mapowaniu content_session_mapping
    3. Jeśli tak, zwraca powiązany session_id
    4. Jeśli nie, zwraca None
    """
    try:
        # Konwertujemy zawartość na string, jeśli to konieczne
        content_str = content
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, sort_keys=True)
        
        # Obliczamy hash zawartości
        content_hash = hashlib.md5(content_str.encode('utf-8')).hexdigest()
        logger.info(f"Obliczony hash zawartości: {content_hash}")
        
        # Sprawdzamy, czy hash istnieje w mapowaniu
        if content_hash in content_session_mapping:
            session_id = content_session_mapping[content_hash]
            logger.info(f"Znaleziono session_id dla hashu {content_hash}: {session_id}")
            return session_id
        
        # Jeśli zawartość to tekst, próbujemy znaleźć wzorce anno_XXXXXXXX
        if isinstance(content, str):
            # Znajdujemy wszystkie wzorce anno_XXXXXXXX
            anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
            anno_matches = anno_pattern.findall(content)
            
            if anno_matches:
                # Tworzymy unikalny "odcisk palca" na podstawie znalezionych wzorców
                anno_fingerprint = ",".join(sorted(set(anno_matches)))
                fingerprint_hash = hashlib.md5(anno_fingerprint.encode('utf-8')).hexdigest()
                
                # Sprawdzamy, czy odcisk palca istnieje w mapowaniu
                if fingerprint_hash in content_session_mapping:
                    session_id = content_session_mapping[fingerprint_hash]
                    logger.info(f"Znaleziono session_id dla odcisku palca {fingerprint_hash}: {session_id}")
                    return session_id
        
        # Nie znaleziono session_id
        logger.info("Nie znaleziono session_id dla podanej zawartości")
        return None
    except Exception as e:
        logger.error(f"Błąd podczas szukania session_id: {str(e)}")
        logger.error(traceback.format_exc())
        return None

# Funkcja do zapisywania mapowania między zawartością a session_id
def store_content_session_mapping(content: str, session_id: str) -> None:
    """Zapisuje mapowanie między zawartością a session_id w bazie danych."""
    try:
        # Generujemy odcisk palca dla zawartości
        fingerprint_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # Sprawdzamy, czy mapowanie już istnieje
        if fingerprint_hash not in content_session_mapping:
            # Jeśli nie, dodajemy nowe mapowanie
            if len(content_session_mapping) >= MAX_CONTENT_MAPPINGS:
                # Usuwamy najstarsze mapowanie, jeśli przekroczyliśmy limit
                oldest_key = next(iter(content_session_mapping))
                del content_session_mapping[oldest_key]
            
            # Zapisujemy mapowanie dla odcisku palca
            content_session_mapping[fingerprint_hash] = session_id
            logger.info(f"Zapisano mapowanie dla odcisku palca {fingerprint_hash} -> session_id {session_id}")
            
            # Znajdujemy wszystkie wzorce anno_XXXXXXXX
            anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
            anno_matches = anno_pattern.findall(content)
            
            # Jeśli znaleziono wzorce anno_XXXXXXXX, generujemy odcisk palca dla każdego z nich
            for anno in anno_matches:
                anno_hash = hashlib.md5(anno.encode('utf-8')).hexdigest()
                content_session_mapping[anno_hash] = session_id
                logger.info(f"Zapisano mapowanie dla tokenu {anno} -> session_id {session_id}")
    except Exception as e:
        logger.error(f"Błąd podczas zapisywania mapowania: {str(e)}")
        logger.error(traceback.format_exc())

# Funkcja do wyciągania tokenów z tekstu, deanonimizacji i wstawiania z powrotem
def extract_deanonymize_replace(data: Any, session_id: str) -> Any:
    """
    Wyciąga tokeny z tekstu, deanonimizuje je i wstawia z powrotem.
    
    Proces:
    1. Serializuje dane do tekstu (jeśli to konieczne)
    2. Wyciąga wszystkie tokeny anno_xxxxx
    3. Deanonimizuje tylko tokeny (nie cały tekst)
    4. Tworzy mapowanie token -> oryginalna wartość
    5. Zastepuje tokeny w oryginalnym tekście
    6. Deserializuje z powrotem do oryginalnego formatu (jeśli to konieczne)
    """
    try:
        # Jeśli dane są już stringiem, nie musimy ich serializować
        if isinstance(data, str):
            serialized_data = data
            is_json = False
        else:
            # Serializujemy dane do JSON
            serialized_data = json.dumps(data, ensure_ascii=False)
            is_json = True
        
        logger.info(f"Rozpoczynam ekstrakcję tokenów z danych o długości {len(serialized_data)}")
        
        # Wyszukujemy wszystkie tokeny anno_xxxxx
        anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
        anno_tokens = anno_pattern.findall(serialized_data)
        
        if not anno_tokens:
            logger.info("Nie znaleziono żadnych tokenów do deanonimizacji")
            return data
        
        # Usuwamy duplikaty i sortujemy
        unique_tokens = sorted(set(anno_tokens))
        logger.info(f"Znaleziono {len(unique_tokens)} unikalnych tokenów do deanonimizacji")
        
        # Deanonimizujemy każdy token osobno
        token_mapping = {}
        for token in unique_tokens:
            try:
                # Wywołujemy API deanonimizacji dla pojedynczego tokenu
                deanonymized_token = deanonymize_text_via_api(token, session_id)
                token_mapping[token] = deanonymized_token.strip()
                logger.info(f"Zdeanonimizowano token {token} -> {deanonymized_token.strip()}")
            except Exception as e:
                logger.error(f"Błąd podczas deanonimizacji tokenu {token}: {str(e)}")
                token_mapping[token] = token  # W przypadku błędu, zostawiamy oryginalny token
        
        logger.info(f"Utworzono mapowanie dla {len(token_mapping)} tokenów")
        
        # Logujemy pierwsze 5 mapowań tokenów, aby zobaczyć, czy są poprawne
        sample_mappings = list(token_mapping.items())[:5]
        logger.info(f"Przykładowe mapowania tokenów: {sample_mappings}")
        
        # Zastepujemy wszystkie tokeny w tekście
        deanonymized_data = serialized_data
        for token, original in token_mapping.items():
            # Upewniamy się, że zastępujemy tylko całe tokeny, a nie części innych tokenów
            pattern = r'\b' + re.escape(token) + r'\b'
            deanonymized_data = re.sub(pattern, original, deanonymized_data)
        
        # Deserializujemy z powrotem do oryginalnego formatu
        if is_json:
            try:
                result = json.loads(deanonymized_data)
                logger.info("Pomyślnie zdeserializowano dane JSON")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Błąd podczas deserializacji JSON: {str(e)}")
                # W przypadku błędu, zwracamy zdeanonimizowany tekst
                return deanonymized_data
        else:
            # Jeśli dane były stringiem, zwracamy zdeanonimizowany string
            return deanonymized_data
    
    except Exception as e:
        logger.error(f"Błąd podczas ekstrakcji i deanonimizacji tokenów: {str(e)}")
        logger.error(traceback.format_exc())
        # W przypadku błędu, zwracamy oryginalne dane
        return data

# Uniwersalne podejście do deanonimizacji
def universal_deanonymization(data: Any, session_id: str) -> Any:
    """
    Uniwersalne podejście do deanonimizacji, które działa niezależnie od struktury dokumentu.
    
    Proces:
    1. Serializuje cały dokument do tekstu
    2. Wyszukuje wszystkie tokeny anno_xxxxx
    3. Tworzy mapowanie token -> oryginalna wartość
    4. Zastepuje wszystkie tokeny w tekście
    5. Deserializuje z powrotem do oryginalnego formatu
    """
    try:
        # Jeśli dane są już stringiem, nie musimy ich serializować
        if isinstance(data, str):
            serialized_data = data
            is_json = False
        else:
            # Serializujemy dane do JSON
            serialized_data = json.dumps(data, ensure_ascii=False)
            is_json = True
        
        logger.info(f"Rozpoczynam uniwersalną deanonimizację danych o długości {len(serialized_data)}")
        
        # Wyszukujemy wszystkie tokeny anno_xxxxx
        anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
        anno_tokens = anno_pattern.findall(serialized_data)
        
        if not anno_tokens:
            logger.info("Nie znaleziono żadnych tokenów do deanonimizacji")
            return data
        
        # Usuwamy duplikaty i sortujemy
        unique_tokens = sorted(set(anno_tokens))
        logger.info(f"Znaleziono {len(unique_tokens)} unikalnych tokenów do deanonimizacji")
        
        # Przygotowujemy tekst z tokenami do deanonimizacji
        tokens_text = " ".join(unique_tokens)
        
        # Wywołujemy API deanonimizacji dla listy tokenów
        deanonymized_text = deanonymize_text_via_api(tokens_text, session_id)
        
        # Parsujemy wynik, zakładając że tokeny są oddzielone spacjami
        deanonymized_tokens = deanonymized_text.split()
        
        # Sprawdzamy, czy liczba tokenów się zgadza
        if len(deanonymized_tokens) != len(unique_tokens):
            logger.warning(f"Liczba zdeanonimizowanych tokenów ({len(deanonymized_tokens)}) nie zgadza się z liczbą tokenów wejściowych ({len(unique_tokens)})")
            # W przypadku błędu, próbujemy deanonimizować każdy token osobno
            token_mapping = {}
            for token in unique_tokens:
                try:
                    deanonymized_token = deanonymize_text_via_api(token, session_id)
                    token_mapping[token] = deanonymized_token.strip()
                except Exception as e:
                    logger.error(f"Błąd podczas deanonimizacji tokenu {token}: {str(e)}")
                    token_mapping[token] = token  # W przypadku błędu, zostawiamy oryginalny token
        else:
            # Tworzymy mapowanie token -> oryginalna wartość
            token_mapping = dict(zip(unique_tokens, deanonymized_tokens))
        
        logger.info(f"Utworzono mapowanie dla {len(token_mapping)} tokenów")
        
        # Zastepujemy wszystkie tokeny w tekście
        deanonymized_data = serialized_data
        logger.info(f"Rozpoczynam zastępowanie {len(token_mapping)} tokenów w tekście o długości {len(serialized_data)}")
        
        # Logujemy pierwsze 5 mapowań tokenów, aby zobaczyć, czy są poprawne
        sample_mappings = list(token_mapping.items())[:5]
        logger.info(f"Przykładowe mapowania tokenów: {sample_mappings}")
        
        for token, original in token_mapping.items():
            # Upewniamy się, że zastępujemy tylko całe tokeny, a nie części innych tokenów
            pattern = r'\b' + re.escape(token) + r'\b'
            count_before = len(re.findall(pattern, deanonymized_data))
            deanonymized_data = re.sub(pattern, original, deanonymized_data)
            count_after = deanonymized_data.count(original) - serialized_data.count(original)
            
            if count_before > 0 and count_before != count_after:
                logger.warning(f"Nieoczekiwana liczba zastąpień dla tokenu {token}: znaleziono {count_before}, zastąpiono {count_after}")
        
        # Deserializujemy z powrotem do oryginalnego formatu
        if is_json:
            try:
                # Logujemy fragment zdeanonimizowanych danych przed deserializacją
                preview_length = min(500, len(deanonymized_data))
                logger.info(f"Fragment zdeanonimizowanych danych przed deserializacją: {deanonymized_data[:preview_length]}...")
                
                result = json.loads(deanonymized_data)
                logger.info("Pomyślnie zdeserializowano dane JSON")
                
                # Logujemy strukturę wyniku
                if isinstance(result, dict):
                    logger.info(f"Struktura wyniku JSON: {list(result.keys())}")
                    if "test_sentences" in result and isinstance(result["test_sentences"], list):
                        logger.info(f"Liczba zdań w test_sentences: {len(result['test_sentences'])}")
                        logger.info(f"Przykładowe zdanie po deanonimizacji: {result['test_sentences'][0]}")
                
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Błąd podczas deserializacji JSON: {str(e)}")
                logger.error(f"Fragment problematycznych danych: {deanonymized_data[:200]}...")
                # W przypadku błędu, zwracamy zdeanonimizowany tekst
                return deanonymized_data
        else:
            # Jeśli dane były stringiem, zwracamy zdeanonimizowany string
            return deanonymized_data
    
    except Exception as e:
        logger.error(f"Błąd podczas uniwersalnej deanonimizacji: {str(e)}")
        logger.error(traceback.format_exc())
        # W przypadku błędu, zwracamy oryginalne dane
        return data

# Stara implementacja - zachowana dla kompatybilności wstecznej
def deanonymize_text_in_json(data: Any, session_id: str) -> Any:
    """
    Rekurencyjna deanonimizacja JSON - stara implementacja, zachowana dla kompatybilności wstecznej.
    Zalecane jest używanie universal_deanonymization zamiast tej funkcji.
    """
    if isinstance(data, dict):
        return {key: deanonymize_text_in_json(value, session_id) for key, value in data.items()}
    elif isinstance(data, list):
        return [deanonymize_text_in_json(item, session_id) for item in data]
    elif isinstance(data, str):
        return deanonymize_text_via_api(data, session_id)
    else:
        return data


# Funkcja do deanonimizacji JSON
def process_deanonymize_json(data: Any, session_id: str) -> Any:
    """
    Deanonimizacja danych w formacie JSON.
    Wykorzystuje funkcję do wyciągania tokenów, deanonimizacji i wstawiania z powrotem.
    """
    return extract_deanonymize_replace(data, session_id)


# Funkcja do anonimizacji XML
def process_xml(root: ET.Element, session_id: str) -> str:
    """Anonimizacja danych w XML."""
    for elem in root.iter():
        if elem.text:
            elem.text = anonymize_text_via_api(elem.text, session_id)
    return ET.tostring(root, encoding='unicode', method='xml')


# Funkcja do deanonimizacji XML
def process_deanonymize_xml(root: ET.Element, session_id: str) -> str:
    """
    Deanonimizacja danych w formacie XML.
    Wykorzystuje funkcję do wyciągania tokenów, deanonimizacji i wstawiania z powrotem.
    """
    # Konwertujemy XML do tekstu
    xml_text = ET.tostring(root, encoding='unicode', method='xml')
    
    # Stosujemy ekstrakcję tokenów, deanonimizację i wstawianie z powrotem
    deanonymized_text = extract_deanonymize_replace(xml_text, session_id)
    
    # Jeśli wynik jest stringiem, parsujemy go z powrotem do XML
    if isinstance(deanonymized_text, str):
        try:
            new_root = ET.fromstring(deanonymized_text)
            return ET.tostring(new_root, encoding='unicode', method='xml')
        except ET.ParseError as e:
            logger.error(f"Błąd podczas parsowania zdeanonimizowanego XML: {str(e)}")
            # W przypadku błędu, zwracamy zdeanonimizowany tekst
            return deanonymized_text
    else:
        # Jeśli wynik nie jest stringiem, zwracamy oryginalny XML
        return xml_text

def anonymize_text_via_api(text: str, session_id: str) -> str:
    """Wysyła tekst do anonymization_service przez API."""
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    max_retries = 3
    retry_delay = 2  # sekundy
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Próba anonimizacji tekstu (długość: {len(text)}) z session_id: {session_id}, próba {attempt+1}/{max_retries}")
            start_time = time.time()
            
            # Dodajemy nagłówki i parametry, aby zapobiec przedwczesnemu zamknięciu połączenia
            headers = {
                "Connection": "keep-alive",
                "Keep-Alive": "timeout=1800, max=1000"
            }
            
            # Tworzymy sesję z długimi timeoutami
            session = requests.Session()
            session.keep_alive = True
            
            # Ustawiamy bardzo wysokie limity czasowe
            response = session.post(
                f"{ANONYMIZATION_URL}/anonymize", 
                json={"session_id": session_id, "text": text},
                timeout=1800,  # 30 minut na przetworzenie dużych plików
                headers=headers
            )
            
            processing_time = time.time() - start_time
            logger.info(f"Czas przetwarzania tekstu: {processing_time:.2f}s")
            
            if response.status_code == 200:
                result = response.json()
                if "anonymized_text" in result:
                    return result["anonymized_text"]
            
            logger.warning(f"Błąd komunikacji z anonymization_service (kod: {response.status_code})")
            logger.warning(f"Treść odpowiedzi: {response.text[:500]}")
            
            if attempt < max_retries - 1:
                logger.info(f"Ponowna próba za {retry_delay} sekund...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Zwiększamy opóźnienie przy każdej próbie
        except requests.RequestException as e:
            logger.error(f"Błąd połączenia z anonymization_service: {str(e)}")
            logger.error(traceback.format_exc())
            if attempt < max_retries - 1:
                logger.info(f"Ponowna próba za {retry_delay} sekund...")
                time.sleep(retry_delay)
                retry_delay *= 2
    
    raise HTTPException(status_code=500, detail="Błąd komunikacji z anonymization_service po wielu próbach")


def deanonymize_text_via_api(text: str, session_id: str) -> str:
    """Wysyła tekst do anonymization_service w celu deanonimizacji przez API."""
    if not text:
        logger.error("Próba deanonimizacji pustego tekstu")
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    # Sprawdzamy, czy session_id istnieje w bazie danych
    session_exists = asyncio.run(check_session_id_exists(session_id))
    if not session_exists:
        logger.warning(f"Session_id {session_id} nie istnieje w bazie danych lub nie zawiera mapowań")
        # Nie rzucamy wyjątku, kontynuujemy, ale logujemy ostrzeżenie
    
    # Sprawdzamy, czy tekst jest tokenem anno_XXXXXXXX
    is_token = re.match(r'^anno_[a-f0-9]{8}$', text.strip()) is not None
    if is_token:
        logger.info(f"Deanonimizacja pojedynczego tokenu: {text}")
    else:
        logger.info(f"Rozpoczynam deanonimizację tekstu o długości {len(text)} z session_id: {session_id}")
    
    max_retries = 3
    retry_delay = 2  # sekundy
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Próba deanonimizacji tekstu (długość: {len(text)}) z session_id: {session_id}, próba {attempt+1}/{max_retries}")
            start_time = time.time()
            
            # Dodajemy nagłówki i parametry, aby zapobiec przedwczesnemu zamknięciu połączenia
            headers = {
                "Connection": "keep-alive",
                "Keep-Alive": "timeout=1800, max=1000"
            }
            
            # Tworzymy sesję z długimi timeoutami
            session = requests.Session()
            session.keep_alive = True
            
            # Przygotowanie danych do wysłania
            payload = {"session_id": session_id, "text": text}
            logger.info(f"Wysyłam żądanie do {ANONYMIZATION_URL}/deanonymize z session_id: {session_id}")
            
            # Ustawiamy bardzo wysokie limity czasowe
            response = session.post(
                f"{ANONYMIZATION_URL}/deanonymize", 
                json=payload,
                timeout=1800,  # 30 minut na przetworzenie dużych plików
                headers=headers
            )
            
            processing_time = time.time() - start_time
            logger.info(f"Otrzymano odpowiedź z anonymization_service, kod: {response.status_code}, czas: {processing_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.info(f"Odpowiedź zdekodowana jako JSON, klucze: {list(result.keys())}")
                    
                    if "deanonymized_text" in result:
                        logger.info(f"Znaleziono klucz 'deanonymized_text' w odpowiedzi, długość tekstu: {len(result['deanonymized_text'])}")
                        return result["deanonymized_text"]
                    else:
                        logger.error(f"Brak klucza 'deanonymized_text' w odpowiedzi: {result}")
                except json.JSONDecodeError as e:
                    logger.error(f"Błąd dekodowania JSON: {str(e)}")
                    logger.error(f"Treść odpowiedzi: {response.text[:500]}")
            
            logger.warning(f"Błąd komunikacji z anonymization_service (kod: {response.status_code})")
            logger.warning(f"Treść odpowiedzi: {response.text[:500]}")
            
            if attempt < max_retries - 1:
                logger.info(f"Ponowna próba za {retry_delay} sekund...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Zwiększamy opóźnienie przy każdej próbie
        except requests.RequestException as e:
            logger.error(f"Błąd połączenia z anonymization_service: {str(e)}")
            logger.error(traceback.format_exc())
            if attempt < max_retries - 1:
                logger.info(f"Ponowna próba za {retry_delay} sekund...")
                time.sleep(retry_delay)
                retry_delay *= 2
    
    logger.error(f"Wszystkie próby deanonimizacji nieudane dla session_id: {session_id}")
    raise HTTPException(status_code=500, detail="Błąd komunikacji z anonymization_service po wielu próbach")

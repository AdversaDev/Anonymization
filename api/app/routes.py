from typing import Any, Dict
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import io
import json
import xml.etree.ElementTree as ET
import requests
import uuid

router = APIRouter()

ANONYMIZATION_URL = "http://anonymization_service:8001"


@router.post("/anonymize")
def anonymize(data: dict) -> Dict[str, Any]:
    response = requests.post(f"{ANONYMIZATION_URL}/anonymize", json=data)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Błąd komunikacji z anonymization_service")
    return response.json()


@router.post("/deanonymize")
def deanonymize(data: dict) -> Dict[str, Any]:
    """Endpoint do przywracania oryginalnych wartości na podstawie session_id."""
    session_id = data.get("session_id", "")
    text = data.get("text", "")
    
    if not session_id or not text:
        raise HTTPException(status_code=400, detail="session_id and text are required")
    
    response = requests.post(f"{ANONYMIZATION_URL}/deanonymize", json={"session_id": session_id, "text": text})
    
    if response.status_code == 200:
        return response.json()
    
    raise HTTPException(status_code=response.status_code, detail="Błąd komunikacji z anonymization_service")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> StreamingResponse:
    """
    Obsługuje przesyłanie plików do anonimizacji z unikalnym session_id
    i zwraca plik do pobrania (download) z dołączonym session_id,
    dzięki czemu plik jest gotowy do deanonimizacji.
    """
    session_id = str(uuid.uuid4())
    
    try:
        content = await file.read()
        filename = file.filename.lower() if file.filename else ""
        
        if filename.endswith((".json", ".fhir")):
            # Pliki JSON i FHIR traktujemy jako JSON
            data = json.loads(content.decode("utf-8"))
            processed_data = process_json(data, session_id)
            # Dołączamy session_id do obiektu JSON, aby był gotowy do deanonimizacji
            if isinstance(processed_data, dict):
                processed_data["session_id"] = session_id
            file_content = json.dumps(processed_data, ensure_ascii=False, indent=2)
            file_bytes = io.BytesIO(file_content.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={session_id}.json"}
            return StreamingResponse(file_bytes, media_type="application/json", headers=headers)
        
        elif filename.endswith(".xml"):
            root = ET.fromstring(content)
            processed_xml = process_xml(root, session_id)
            # Dodajemy nowy element <session_id> na początku XML
            root.insert(0, ET.Element("session_id"))
            root[0].text = session_id
            final_xml = ET.tostring(root, encoding='unicode', method='xml')
            file_bytes = io.BytesIO(final_xml.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={session_id}.xml"}
            return StreamingResponse(file_bytes, media_type="application/xml", headers=headers)
        
        elif filename.endswith(".txt"):
            text = content.decode("utf-8")
            processed_text = anonymize_text_via_api(text, session_id)
            # Dodajemy linię z session_id na początku pliku tekstowego
            final_text = f"SessionID: {session_id}\n" + processed_text
            file_bytes = io.BytesIO(final_text.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={session_id}.txt"}
            return StreamingResponse(file_bytes, media_type="text/plain", headers=headers)
        
        else:
            raise HTTPException(status_code=415, detail="Unsupported file format")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.post("/upload-deanonymize")
async def upload_deanonymize_file(file: UploadFile = File(...)) -> StreamingResponse:
    """
    Obsługuje przesyłanie plików do deanonimizacji.
    Plik musi zawierać oryginalny session_id, który zostanie użyty do przywrócenia danych.
    Wynik jest zwracany jako plik do pobrania.
    """
    try:
        content = await file.read()
        filename = file.filename.lower() if file.filename else ""
        
        # Przetwarzanie plików JSON/FHIR
        if filename.endswith((".json", ".fhir")):
            data = json.loads(content.decode("utf-8"))
            if "session_id" in data:
                original_session = data["session_id"]
                del data["session_id"]
            else:
                raise HTTPException(status_code=400, detail="Brak session_id w pliku JSON do deanonimizacji")
            processed_data = process_deanonymize_json(data, original_session)
            # Możesz opcjonalnie dodać session_id do wyniku, jeśli potrzebujesz
            file_content = json.dumps(processed_data, ensure_ascii=False, indent=2)
            file_bytes = io.BytesIO(file_content.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={original_session}_deanon.json"}
            return StreamingResponse(file_bytes, media_type="application/json", headers=headers)
        
        # Przetwarzanie plików XML
        elif filename.endswith(".xml"):
            root = ET.fromstring(content)
            # Zakładamy, że pierwszy element (child) to <session_id>
            if len(root) > 0 and root[0].tag == "session_id":
                original_session = root[0].text
                if original_session is None:
                    raise HTTPException(status_code=400, detail="Brak session_id w XML do deanonimizacji")
                root.remove(root[0])
            else:
                raise HTTPException(status_code=400, detail="Brak session_id w XML do deanonimizacji")
            processed_xml = process_deanonymize_xml(root, original_session)
            file_bytes = io.BytesIO(processed_xml.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={original_session}_deanon.xml"}
            return StreamingResponse(file_bytes, media_type="application/xml", headers=headers)
        
        # Przetwarzanie plików TXT
        elif filename.endswith(".txt"):
            text = content.decode("utf-8")
            lines = text.splitlines()
            if lines and lines[0].startswith("SessionID:"):
                original_session = lines[0].split("SessionID:")[1].strip()
                text_to_process = "\n".join(lines[1:])  # usuń linię z sessionID
            else:
                raise HTTPException(status_code=400, detail="Brak sessionID w pliku TXT do deanonimizacji")
            processed_text = deanonymize_text_via_api(text_to_process, original_session)
            # Zwracamy wynik bez dodatkowego dodawania sessionID
            file_bytes = io.BytesIO(processed_text.encode("utf-8"))
            headers = {"Content-Disposition": f"attachment; filename={original_session}_deanon.txt"}
            return StreamingResponse(file_bytes, media_type="text/plain", headers=headers)
        
        else:
            raise HTTPException(status_code=415, detail="Unsupported file format")
    
    except Exception as e:
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


# Rekurencyjna deanonimizacja JSON
def deanonymize_text_in_json(data: Any, session_id: str) -> Any:
    if isinstance(data, dict):
        return {key: deanonymize_text_in_json(value, session_id) for key, value in data.items()}
    elif isinstance(data, list):
        return [deanonymize_text_in_json(item, session_id) for item in data]
    elif isinstance(data, str):
        return deanonymize_text_via_api(data, session_id)
    else:
        return data


def process_deanonymize_json(data: dict, session_id: str) -> Any:
    """Deanonimizacja danych w formacie JSON."""
    return deanonymize_text_in_json(data, session_id)


def process_xml(root: ET.Element, session_id: str) -> str:
    """Anonimizacja danych w XML."""
    for elem in root.iter():
        if elem.text:
            elem.text = anonymize_text_via_api(elem.text, session_id)
    return ET.tostring(root, encoding='unicode', method='xml')


def process_deanonymize_xml(root: ET.Element, session_id: str) -> str:
    """Deanonimizacja danych w XML."""
    for elem in root.iter():
        if elem.text:
            elem.text = deanonymize_text_via_api(elem.text, session_id)
    return ET.tostring(root, encoding='unicode', method='xml')


def anonymize_text_via_api(text: str, session_id: str) -> str:
    """Wysyła tekst do anonymization_service przez API."""
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    response = requests.post(f"{ANONYMIZATION_URL}/anonymize", json={"session_id": session_id, "text": text})
    if response.status_code == 200:
        result = response.json()
        if "anonymized_text" in result:
            return result["anonymized_text"]
    raise HTTPException(status_code=response.status_code, detail="Błąd komunikacji z anonymization_service")


def deanonymize_text_via_api(text: str, session_id: str) -> str:
    """Wysyła tekst do anonymization_service w celu deanonimizacji przez API."""
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    response = requests.post(f"{ANONYMIZATION_URL}/deanonymize", json={"session_id": session_id, "text": text})
    if response.status_code == 200:
        result = response.json()
        if "deanonymized_text" in result:
            return result["deanonymized_text"]
    raise HTTPException(status_code=response.status_code, detail="Błąd komunikacji z anonymization_service")

from fastapi import APIRouter, File, UploadFile, HTTPException
import json
import xml.etree.ElementTree as ET
from anonymization.app.anonymizer import anonymize_text

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Endpoint do przesyłania plików i anonimizacji ich zawartości.
    Obsługuje formaty: JSON, XML, TXT.
    """
    try:
        content = await file.read()
        filename = file.filename.lower()
        
        if filename.endswith(".json"):
            data = json.loads(content)
            anonymized_data = process_json(data)
            return {"anonymized_data": anonymized_data}
        
        elif filename.endswith(".xml"):
            root = ET.fromstring(content)
            anonymized_xml = process_xml(root)
            return {"anonymized_xml": anonymized_xml}
        
        elif filename.endswith(".txt"):
            text = content.decode("utf-8")
            anonymized_text = anonymize_text(text)
            return {"anonymized_text": anonymized_text}
        
        else:
            raise HTTPException(status_code=415, detail="Unsupported file format")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

def process_json(data: dict) -> dict:
    """Anonimizacja danych w formacie JSON (FHIR itp.)."""
    if "text" in data:
        data["text"] = anonymize_text(data["text"])
    return data


def process_xml(root: ET.Element) -> str:
    """Anonimizacja danych w XML z poprawnym oznaczeniem lokalizacji i ulic."""
    for elem in root.iter():
        if elem.text:
            anonymized = anonymize_text(elem.text)
            if "PERSON" in anonymized and elem.tag == "city":
                anonymized = anonymized.replace("PERSON", "LOCATION")
            if "PERSON" in anonymized and elem.tag == "street":
                anonymized = anonymized.replace("PERSON", "STREET")
            if "LOCATION" in anonymized and elem.tag == "street":
                anonymized = anonymized.replace("LOCATION", "STREET")
            elem.text = anonymized
    
    # Konwersja XML na string bez encji
    return ET.tostring(root, encoding='unicode', method='xml')


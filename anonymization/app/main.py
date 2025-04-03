from fastapi import FastAPI, HTTPException
from app.anonymizer import AnonymizationService

import uuid

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Anonymization Service is running"}

service = AnonymizationService()

@app.post("/anonymize")
def anonymize(data: dict):
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    session_id = str(uuid.uuid4())  # Generowanie unikalnego session_id
    anonymized_text = service.anonymize_text(session_id, text)  # ✅ Teraz używa klasy!

    return {"session_id": session_id, "anonymized_text": anonymized_text}

@app.post("/deanonymize")
def deanonymize(data: dict):
    session_id = data.get("session_id", "")
    text = data.get("text", "")

    if not session_id or not text:
        raise HTTPException(status_code=400, detail="session_id and text are required")

    deanonymized_text = service.deanonymize_text(session_id, text)  # ✅ Używa klasy!

    return {"deanonymized_text": deanonymized_text}

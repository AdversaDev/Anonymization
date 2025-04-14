from fastapi import FastAPI, HTTPException
from app.anonymizer import AnonymizationService, get_db_connection

import uuid

app = FastAPI()

@app.get("/")
async def home():
    return {"message": "Anonymization Service is running"}

service = AnonymizationService()

@app.post("/anonymize")
async def anonymize(data: dict):
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    # Sprawdzamy, czy użytkownik podał session_id
    session_id = data.get("session_id")
    if not session_id:
        # Jeśli nie, generujemy nowy session_id
        session_id = str(uuid.uuid4())
    
    anonymized_text = service.anonymize_text(session_id, text)  # ✅ Teraz używa klasy!

    return {"session_id": session_id, "anonymized_text": anonymized_text}

@app.post("/deanonymize")
async def deanonymize(data: dict):
    session_id = data.get("session_id", "")
    text = data.get("text", "")

    if not session_id or not text:
        raise HTTPException(status_code=400, detail="session_id and text are required")

    deanonymized_text = service.deanonymize_text(session_id, text)  # ✅ Używa klasy!

    return {"deanonymized_text": deanonymized_text}


@app.post("/create-mapping")
async def create_mapping(data: dict):
    """
    Tworzy mapowanie tokenu do oryginalnej wartości w bazie danych.
    Wymaga: session_id, anon_id, original_value
    Opcjonalnie: entity_type
    """
    session_id = data.get("session_id", "")
    anon_id = data.get("anon_id", "")
    original_value = data.get("original_value", "")
    entity_type = data.get("entity_type", "UNKNOWN")

    if not session_id or not anon_id or not original_value:
        raise HTTPException(status_code=400, detail="session_id, anon_id i original_value są wymagane")
    
    # Sprawdzamy, czy token ma poprawny format (anno_XXXXXXXX)
    if not anon_id.startswith("anno_") or len(anon_id) != 13:
        # Jeśli nie, dodajemy prefix anno_ jeśli go nie ma
        if not anon_id.startswith("anno_"):
            anon_id = f"anno_{anon_id}"
        # Jeśli token jest za krótki, uzupełniamy go losowymi znakami
        if len(anon_id) < 13:
            import random
            import string
            while len(anon_id) < 13:
                anon_id += random.choice(string.hexdigits.lower())
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Najpierw sprawdzamy, czy istnieje już mapowanie dla tego tokenu i session_id
        cursor.execute(
            "SELECT id FROM anonymization WHERE session_id = %s AND anon_id = %s",
            (session_id, anon_id)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Jeśli istnieje, aktualizujemy
            cursor.execute(
                "UPDATE anonymization SET original_value = %s, entity_type = %s WHERE session_id = %s AND anon_id = %s",
                (original_value, entity_type, session_id, anon_id)
            )
        else:
            # Jeśli nie istnieje, dodajemy nowe
            cursor.execute(
                "INSERT INTO anonymization (session_id, anon_id, original_value, entity_type) VALUES (%s, %s, %s, %s)",
                (session_id, anon_id, original_value, entity_type)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"status": "success", "message": "Mapowanie utworzone pomyślnie"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd podczas tworzenia mapowania: {str(e)}")

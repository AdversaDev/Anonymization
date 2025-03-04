from fastapi import FastAPI
from anonymization.app.anonymizer import anonymize_text

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Anonymization Service is running"}

@app.post("/anonymize")
def anonymize(data: dict):
    text = data.get("text", "")
    anonymized_text = anonymize_text(text)
    return {"anonymized_text": anonymized_text}

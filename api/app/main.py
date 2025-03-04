from fastapi import FastAPI
import requests
from api.app.routes import router

app = FastAPI()

app.include_router(router)  # Musisz dodać router!

ANONYMIZATION_URL = "http://anonymization_service:8001/anonymize"

@app.post("/process")
def process_data(data: dict):
    response = requests.post(ANONYMIZATION_URL, json=data)
    return response.json()

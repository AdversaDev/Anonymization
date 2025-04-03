from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import SpacyNlpEngine, NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer import Pattern, PatternRecognizer
import requests
from fastapi import HTTPException
import psycopg2
import os
import uuid
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Przykładowe przypisanie session_id
session_id = str(uuid.uuid4())

ANONYMIZATION_URL = "http://anonymization_service:8001"



DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anon_user:securepassword@db/anon_db")
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)



# Inicjalizacja NLP
config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}]
}

nlp_engine = NlpEngineProvider(nlp_configuration=config).create_engine()
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["de"])
anonymizer = AnonymizerEngine()

# Lista fraz, które NIE powinny być anonimizowane
IGNORED_PHRASES = {"mein name", "meine kreditkartennummer", "mein iban", "mein code", "ich", "ich wohne", "meine", "mein", "und", "in", "der", "am", "ist", "das", "die", "den", "dem", "ein", "eine", "meine telefonnummer", "meine steuernummer"}

# Funkcja sprawdzająca, czy dany tekst zawiera frazę do ignorowania
def is_ignored(text):
    return text.lower() in IGNORED_PHRASES

# Regex dla numerów telefonów (bez `CREDIT_CARD` i `TAX_ID`)
PHONE_NUMBER_REGEX = r"\b(?:\+49\s?\d{1,3}[\s-]?\d{3,5}[\s-]?\d{4,6})\b"

# Regex dla Steuernummer
TAX_ID_REGEX = r"\b\d{2}/\d{3}/\d{5}\b|\b\d{3}/\d{3}/\d{5}\b|\b\d{10,11}\b"

# Regex dla kart płatniczych (Visa, MasterCard, Amex, Maestro)
CREDIT_CARD_REGEX = (
    r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|36\d{2}|(?:50|56|57|58|59|6[0-9])\d{2})"
    r"[\s-]?\d{4}[\s-]?\d{4,7}[\s-]?\d{0,4}\b"
)

# Regex dla kodów pocztowych
ZIP_CODE_REGEX = r"\b\d{5}\b|\b\d{2}-\d{3}\b"

# **POPRAWIONY regex dla dat**
DATE_REGEX = (
    r"\b\d{1,2}\.\s(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s\d{4}\b"
    r"|\b\d{1,2}-\d{1,2}-\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{4}\b"
)

# ✅ Testujemy regex przed użyciem w Presidio
STREET_REGEX = r"(?<!\w)(?:[A-ZÄÖÜa-zäöüß]+(?:[-][A-ZÄÖÜa-zäöüß]+)*)\s(?:Straße|straße|Weg|Platz|Allee|Ring|Gasse|Damm|Steig|Ufer|Hof|Chaussee)\s\d+(?!\w)"

# Regex dla adresów e-mail
EMAIL_REGEX = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"

# Regex dla IBAN
IBAN_REGEX = r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b"

DOCTOR_REGEX = r"\b(?:Dr\.?\s[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b"

ORG_REGEX = r"\b(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s(?:AG|GmbH|Klinik|Universität|Versicherung|Krankenhaus|Bank))\b"


# **Dodanie detektorów do Presidio**

email_pattern = Pattern(name="EMAIL", regex=EMAIL_REGEX, score=1.0)
email_recognizer = PatternRecognizer(supported_entity="EMAIL", patterns=[email_pattern])
analyzer.registry.add_recognizer(email_recognizer)

iban_pattern = Pattern(name="IBAN", regex=IBAN_REGEX, score=1.0)
iban_recognizer = PatternRecognizer(supported_entity="IBAN", patterns=[iban_pattern])
analyzer.registry.add_recognizer(iban_recognizer)

zip_code_pattern = Pattern(name="ZIP_CODE", regex=ZIP_CODE_REGEX, score=1.0)
zip_code_recognizer = PatternRecognizer(supported_entity="ZIP_CODE", patterns=[zip_code_pattern])
analyzer.registry.add_recognizer(zip_code_recognizer)

date_pattern = Pattern(name="DATE", regex=DATE_REGEX, score=1.0)
date_recognizer = PatternRecognizer(supported_entity="DATE", patterns=[date_pattern])
analyzer.registry.add_recognizer(date_recognizer)

credit_card_pattern = Pattern(name="CREDIT_CARD", regex=CREDIT_CARD_REGEX, score=1.0)
credit_card_recognizer = PatternRecognizer(supported_entity="CREDIT_CARD", patterns=[credit_card_pattern])
analyzer.registry.add_recognizer(credit_card_recognizer)

tax_id_pattern = Pattern(name="TAX_ID", regex=TAX_ID_REGEX, score=1.0)
tax_id_recognizer = PatternRecognizer(supported_entity="TAX_ID", patterns=[tax_id_pattern])
analyzer.registry.add_recognizer(tax_id_recognizer)

phone_pattern = Pattern(name="PHONE_NUMBER", regex=PHONE_NUMBER_REGEX, score=1.0)
phone_recognizer = PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[phone_pattern])
analyzer.registry.add_recognizer(phone_recognizer)

street_pattern = Pattern(name="STREET", regex=STREET_REGEX, score=1.5)
street_recognizer = PatternRecognizer(supported_entity="STREET", patterns=[street_pattern])
analyzer.registry.add_recognizer(street_recognizer)

org_pattern = Pattern(name="ORG", regex=ORG_REGEX, score=1.0)
org_recognizer = PatternRecognizer(supported_entity="ORG", patterns=[org_pattern])
analyzer.registry.add_recognizer(org_recognizer)

doctor_pattern = Pattern(name="DOCTOR", regex=DOCTOR_REGEX, score=1.0)
doctor_recognizer = PatternRecognizer(supported_entity="DOCTOR", patterns=[doctor_pattern])
analyzer.registry.add_recognizer(doctor_recognizer)

def anonymize_text_via_api(text: str, session_id: str) -> str:
    """Wysyła tekst do anonymization_service przez API, z sesją."""
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    response = requests.post(ANONYMIZATION_URL, json={"session_id": session_id, "text": text})

    if response.status_code == 200:
        result = response.json()
        return result.get("anonymized_text", text)

    raise HTTPException(status_code=response.status_code, detail="Błąd komunikacji z anonymization_service")

def preprocess_street_names(text):
    """
    Rozdziela fragmenty takie jak 'Hauptstraße' na 'Haupt straße',
    aby poprawić wykrywanie przez Presidio.
    """
    street_patterns = [
        r"([A-ZÄÖÜa-zäöüß-]+)(straße)",   # np. Hauptstraße -> Haupt straße
        r"([A-ZÄÖÜa-zäöüß-]+)(Straße)",   # np. SiemensStraße -> Siemens Straße
    ]

    for pattern in street_patterns:
        text = re.sub(pattern, r"\1 \2", text)  # Wstawia spację między nazwą a "straße"

    return text

def expand_street_abbreviations(text):
    """
    Zamienia skróty nazw ulic (Str., Pl., Al.) na pełne wersje.
    """
    abbreviations = {
        r"\bStr\.\b": "Straße",
        r"\bPl\.\b": "Platz",
        r"\bAl\.\b": "Allee"
    }
    
    for abbr, full_form in abbreviations.items():
        # Obsługuje przypadki zarówno z myślnikiem, jak i bez niego
        text = re.sub(rf"(\b[A-ZÄÖÜa-zäöüß-]+\b)[-\s]+{abbr}", rf"\1 {full_form}", text)

    return text

def normalize_street_names(text):
    """
    Zamienia myślniki na spacje w nazwach ulic, aby poprawić wykrywanie w Presidio.
    """
    return re.sub(r"(\b[A-ZÄÖÜa-zäöüß]+)-([A-ZÄÖÜa-zäöüß]+)-([A-ZÄÖÜa-zäöüß]+)\s(Straße|straße|Weg|Platz|Allee|Ring|Gasse|Damm|Steig|Ufer|Hof|Chaussee)\s\d+",
                  r"\1 \2 \3 \4", text)

def detect_street(text: str) -> list:
    detected_streets = []
    for match in re.finditer(STREET_REGEX, text):
        print(f"📌 Wykryto STREET ręcznie: {match.group()}")  # ✅ Debugowanie wykrytych ulic
        detected_streets.append(RecognizerResult(start=match.start(), end=match.end(), entity_type="STREET", score=1.0))
    return detected_streets

# **Ręczna detekcja ZIP_CODE**
def detect_zip_code(text: str) -> list:
    detected_zip_codes = []
    for match in re.finditer(ZIP_CODE_REGEX, text):
        print(f"📌 Wykryto ZIP_CODE: {match.group()}")  # Debugowanie
        detected_zip_codes.append(RecognizerResult(start=match.start(), end=match.end(), entity_type="ZIP_CODE", score=1.0))
    return detected_zip_codes

# **Ręczna detekcja DATE**
def detect_dates(text: str) -> list:
    detected_dates = []
    for match in re.finditer(DATE_REGEX, text, re.IGNORECASE):
        print(f"📌 Wykryto DATE: {match.group()}")  # Debugowanie
        detected_dates.append(RecognizerResult(start=match.start(), end=match.end(), entity_type="DATE", score=1.0))
    return detected_dates

def detect_credit_cards(text: str) -> list:
    detected_cards = []
    for match in re.finditer(CREDIT_CARD_REGEX, text):
        print(f"📌 Wykryto numer karty: {match.group()}")  # Debugowanie
        detected_cards.append(RecognizerResult(start=match.start(), end=match.end(), entity_type="CREDIT_CARD", score=1.0))
    return detected_cards

# **Ręczna detekcja `TAX_ID`**
def detect_tax_id(text: str) -> list:
    detected_tax_ids = []
    for match in re.finditer(TAX_ID_REGEX, text):
        print(f"📌 Wykryto Steuernummer: {match.group()}")  # Debugowanie
        detected_tax_ids.append(RecognizerResult(start=match.start(), end=match.end(), entity_type="TAX_ID", score=1.0))
    return detected_tax_ids


def anonymize_text(session_id: str, text: str) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        zip_code_results = detect_zip_code(text)
        date_results = detect_dates(text)
        credit_card_results = detect_credit_cards(text)
        tax_id_results = detect_tax_id(text)
        street_results = detect_street(text)

        results = analyzer.analyze(text=text, language="de")

        filtered_results = zip_code_results + date_results + credit_card_results + tax_id_results + street_results

        for result in results:
            extracted_text = text[result.start:result.end]

            if result.entity_type == "PHONE_NUMBER":
                if re.match(CREDIT_CARD_REGEX, extracted_text):
                    print(f"🔄 Zmieniam `PHONE_NUMBER` na `CREDIT_CARD`: {extracted_text}")
                    result.entity_type = "CREDIT_CARD"
                elif re.match(TAX_ID_REGEX, extracted_text):
                    print(f"🔄 Zmieniam `PHONE_NUMBER` na `TAX_ID`: {extracted_text}")
                    result.entity_type = "TAX_ID"

            if not is_ignored(extracted_text):
                filtered_results.append(result)

        print("\n📌 Wykryte encje przed anonimizacją:")
        for res in filtered_results:
            print(f"- {res.entity_type}: {text[res.start:res.end]}")

        anonymized_text = anonymizer.anonymize(text=text, analyzer_results=filtered_results)
        
        for res in filtered_results:
            extracted_text = text[res.start:res.end]
            cursor.execute(
                "INSERT INTO anonymization (session_id, original_value, entity_type) VALUES (%s, %s, %s)",
                (session_id, extracted_text, res.entity_type)
            )
            conn.commit()
            text = re.sub(rf"\b{re.escape(extracted_text)}\b", "[ANONYMIZED]", text)
        
        cursor.close()
        conn.close()
        return text
    
    except Exception as e:
        cursor.close()
        conn.close()
        return f"Error during anonymization: {str(e)}"
    
def deanonymize_text(session_id: str, text: str) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT anon_id, original_value FROM anonymization WHERE session_id = %s", (session_id,))
    mappings = cursor.fetchall()

    for anon_id, original_value in mappings:
        text = text.replace(anon_id, original_value)

    cursor.close()
    conn.close()
    
    return text




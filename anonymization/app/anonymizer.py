from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import SpacyNlpEngine, NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer import Pattern, PatternRecognizer

import re

# Inicjalizacja NLP
config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "de", "model_name": "de_core_news_sm"}]
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

# Regex dla niemieckich nazw ulic z numerami (np. "Berliner Straße 12", "Hauptstraße 5")
STREET_REGEX = r"\b[A-ZÄÖÜa-zäöüß]+\s(?:Straße|Weg|Platz|Allee|Ring|Gasse|Damm|Steig|Ufer|Hof|Chaussee)\s\d+\b"


# **Dodanie detektorów do Presidio**

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

street_pattern = Pattern(name="STREET", regex=STREET_REGEX, score=1.0)
street_recognizer = PatternRecognizer(supported_entity="STREET", patterns=[street_pattern])
analyzer.registry.add_recognizer(street_recognizer)

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

def anonymize_text(text: str) -> str:
    """
    Anonimizuje dane osobowe w podanym tekście.
    """
    try:
        # **KROK 1: Wykrywamy `DATE`, żeby uniknąć konfliktów**
        zip_code_results = detect_zip_code(text)
        date_results = detect_dates(text)
        credit_card_results = detect_credit_cards(text)
        tax_id_results = detect_tax_id(text)

        # **KROK 2: Analiza tekstu (Presidio)**
        results = analyzer.analyze(text=text, language="de")

        # **KROK 3: Filtracja wyników (ignorowanie fraz typu "Mein Name")**
        filtered_results = zip_code_results + date_results + credit_card_results + tax_id_results   # Zaczynamy od `DATE`

        for result in results:
            extracted_text = text[result.start:result.end]

            # **Jeśli `PHONE_NUMBER` jest `CREDIT_CARD` lub `TAX_ID`, poprawiamy jego kategorię**
            if result.entity_type == "PHONE_NUMBER":
                if re.match(CREDIT_CARD_REGEX, extracted_text):
                    print(f"🔄 Zmieniam `PHONE_NUMBER` na `CREDIT_CARD`: {extracted_text}")
                    result.entity_type = "CREDIT_CARD"
                elif re.match(TAX_ID_REGEX, extracted_text):
                    print(f"🔄 Zmieniam `PHONE_NUMBER` na `TAX_ID`: {extracted_text}")
                    result.entity_type = "TAX_ID"

            if not is_ignored(extracted_text):
                filtered_results.append(result)

        # **DEBUG: Sprawdzamy, co wykrył system**
        print("\n📌 Wykryte encje przed anonimizacją:")
        for res in filtered_results:
            print(f"- {res.entity_type}: {text[res.start:res.end]}")

        # **KROK 4: Anonimizacja wykrytych danych**
        anonymized_text = anonymizer.anonymize(text=text, analyzer_results=filtered_results)

        return anonymized_text.text
    
    except Exception as e:
        return f"Error during anonymization: {str(e)}"

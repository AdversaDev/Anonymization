import os
import re
import uuid
import psycopg2
import logging
from presidio_analyzer import AnalyzerEngine, RecognizerResult, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguracja bazy danych
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anon_user:securepassword@db/anon_db")

def get_db_connection():
    """Nawiązuje połączenie z bazą danych."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error("Błąd połączenia z bazą danych: %s", e)
        raise

# Konfiguracja NLP (dla języka niemieckiego)
NLP_CONFIG = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}]
}
nlp_engine = NlpEngineProvider(nlp_configuration=NLP_CONFIG).create_engine()
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["de"])
anonymizer = AnonymizerEngine()  # Choć nie wykorzystujemy go bezpośrednio, inicjalizacja jest zachowana.

# Lista fraz, które NIE powinny być anonimizowane
IGNORED_PHRASES = {
    "mein name", "krankenversicherungsnummer", "meine kreditkartennummer",
    "mein iban", "mein code", "ich", "ich wohne", "meine", "mein", "und",
    "in", "der", "am", "ist", "das", "die", "den", "dem", "ein", "eine",
    "meine telefonnummer", "meine steuernummer"
}

def is_ignored(text: str) -> bool:
    """Sprawdza, czy dany fragment powinien być pominięty przy anonimizacji."""
    return text.lower() in IGNORED_PHRASES

# Definicje regexów
PHONE_NUMBER_REGEX = (
    r"\b(?:\+49[\s\-]?\d{1,3}[\s\-]?\d{1,4}[\s\-]?\d{4,6})\b"  # np. +49 170 1234567
    r"|\b(?:0\d{2,3}[\s\-]?\d{3,5}[\s\-]?\d{4,6})\b"              # np. 089 123 4567
    r"|\b(?:\+49\d{10,13})\b"                                     # np. +491701234567
    r"|\b(?:\d{3,4}[\s\-]?\d{6,8})\b"                             # np. 030-12345678
)

TAX_ID_REGEX = r"\b\d{2}/\d{3}/\d{5}\b|\b\d{3}/\d{3}/\d{5}\b|\b\d{10,11}\b"

CREDIT_CARD_REGEX = (
    r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|36\d{2}|(?:50|56|57|58|59|6[0-9])\d{2})"
    r"[\s-]?\d{4}[\s-]?\d{4,7}[\s-]?\d{0,4}\b"
)

ZIP_CODE_REGEX = r"\b\d{5}\b|\b\d{2}-\d{3}\b"

DATE_REGEX = (
    # Format with dot: 15. Januar 1910
    r"\b\d{1,2}\.\s(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s\d{4}\b"
    # Format without dot: 15 Januar 1910
    r"|\b\d{1,2}\s(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s\d{4}\b"
    # Format with abbreviated month names with dot: 15. Jan. 1910
    r"|\b\d{1,2}\.\s(?:Jan\.|Feb\.|Mär\.|Apr\.|Mai\.|Jun\.|Jul\.|Aug\.|Sep\.|Okt\.|Nov\.|Dez\.)\s\d{4}\b"
    # Format with abbreviated month names without dot: 15 Jan 1910
    r"|\b\d{1,2}\s(?:Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\s\d{4}\b"
    # Numeric formats
    r"|\b\d{1,2}-\d{1,2}-\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{4}\b"
    # Additional common German date formats
    r"|\b\d{1,2}\.\d{1,2}\.\d{4}\b"
    r"|\b\d{1,2}\.\d{1,2}\.\d{2}\b"
)

# German license plate pattern: 1-3 letters (city code), 1-2 letters (optional), 1-4 digits
# Examples: M AB 123, B C 1, HH AB 1234, etc.
LICENSE_PLATE_REGEX = r"\b[A-ZÄÖÜ]{1,3}(?:[-\s][A-ZÄÖÜ]{1,2})?[-\s][1-9]\d{0,3}\b"

# Ulepszony regex dla nazw ulic – teraz dopuszcza opcjonalną spację między nazwą a przyrostkiem
STREET_REGEX = (
    r"(?<!\w)(?:[A-ZÄÖÜa-zäöüß]+(?:[-][A-ZÄÖÜa-zäöüß]+)*)(?:\s)?"
    r"(Straße|Weg|Platz|Allee|Ring|Gasse|Damm|Steig|Ufer|Hof|Chaussee)\s\d+(?!\w)"
)

# Lista popularnych niemieckich imion
GERMAN_NAMES = [
    # Imiona zaczynające się na E
    "Eva", "Emma", "Elisa", "Elena", "Ella", "Erika", "Emilia", "Elisabeth", "Ewa", "Eleonora",
    "Erna", "Esmeralda", "Elina", "Elvira", "Edda", "Edeltraut", "Editha", "Elke", "Elsa", "Edelgard",
    # Inne popularne imiona żeńskie
    "Anna", "Maria", "Sophie", "Laura", "Lena", "Hannah", "Leonie", "Katharina", "Julia", "Sarah",
    "Lisa", "Johanna", "Nora", "Mia", "Charlotte", "Sophia", "Greta", "Luisa", "Clara", "Amelie",
    # Popularne imiona męskie
    "Thomas", "Michael", "Andreas", "Stefan", "Peter", "Christian", "Martin", "Alexander", "Markus", "Frank",
    "Klaus", "Jürgen", "Hans", "Uwe", "Dieter", "Wolfgang", "Matthias", "Werner", "Helmut", "Rainer",
    "Jan", "Lukas", "Felix", "Maximilian", "Paul", "Florian", "David", "Tim", "Jonas", "Niklas"
]

# Regex dla imion
NAME_REGEX = r"\b(?:" + "|".join(GERMAN_NAMES) + r")\b"

# Rejestracja własnych detektorów w analizatorze Presidio
def detect_names(text: str) -> list:
    """Wykrywa imiona w tekście przy użyciu wzorca regex."""
    results = []
    for name in GERMAN_NAMES:
        # Szukamy dokładnych dopasowań imion
        for match in re.finditer(r'\b' + re.escape(name) + r'\b', text):
            start = match.start()
            end = match.end()
            results.append(
                RecognizerResult(
                    entity_type="PERSON",
                    start=start,
                    end=end,
                    score=0.95
                )
            )
    return results

def register_custom_recognizers():
    custom_entities = [
        ("ZIP_CODE", ZIP_CODE_REGEX, 1.0),
        ("DATE", DATE_REGEX, 1.0),
        ("CREDIT_CARD", CREDIT_CARD_REGEX, 1.0),
        ("TAX_ID", TAX_ID_REGEX, 1.0),
        ("PHONE_NUMBER", PHONE_NUMBER_REGEX, 1.0),
        ("STREET", STREET_REGEX, 1.5),
        ("LICENSE_PLATE", LICENSE_PLATE_REGEX, 1.0),
        ("PERSON", NAME_REGEX, 0.95)  # Zwiększamy priorytet rozpoznawania imion
    ]
    for entity, regex, score in custom_entities:
        pattern = Pattern(name=entity, regex=regex, score=score)
        recognizer = PatternRecognizer(supported_entity=entity, patterns=[pattern])
        analyzer.registry.add_recognizer(recognizer)

register_custom_recognizers()

# Funkcje normalizujące nazwy ulic
def expand_street_abbreviations(text: str) -> str:
    """Rozszerza skróty nazw ulic, np. 'Str.' na 'Straße'."""
    abbreviations = {
        r"\bStr\.\b": "Straße",
        r"\bPl\.\b": "Platz",
        r"\bAl\.\b": "Allee",
        r"\bStr\b": "Straße",
        r"\bPl\b": "Platz",
        r"\bAl\b": "Allee"
    }
    for abbr, full_form in abbreviations.items():
        text = re.sub(rf"(\b[A-ZÄÖÜa-zäöüß-]+\b)[-\s]?{abbr}", rf"\1 {full_form}", text)
    return text

def preprocess_street_names(text: str) -> str:
    """
    Dzieli złożone nazwy ulic, np. 'Hauptstraße' → 'Haupt straße', ale nie modyfikuje
    nazw zawierających myślnik tuż przed przyrostkiem (np. 'Werner-von-Siemens-Straße' pozostaje niezmienione).
    """
    street_patterns = [
        r"\b([A-ZÄÖÜa-zäöüß-]+)(straße)\b",
        r"\b([A-ZÄÖÜa-zäöüß-]+)(Straße)\b",
        r"\b([A-ZÄÖÜa-zäöüß-]+)(weg)\b",
        r"\b([A-ZÄÖÜa-zäöüß-]+)(platz)\b",
        r"\b([A-ZÄÖÜa-zäöüß-]+)(allee)\b",
        r"\b([A-ZÄÖÜa-zäöüß-]+)(gasse)\b",
        r"\b([A-ZÄÖÜa-zäöüß-]+)(ring)\b",
        r"\b([A-ZÄÖÜa-zäöüß-]+)(damm)\b",
        r"\b([A-ZÄÖÜa-zäöüß-]+)(ufer)\b",
    ]
    for pattern in street_patterns:
        text = re.sub(
            pattern,
            lambda m: m.group(1) + ("" if m.group(1).endswith('-') else " ") + m.group(2),
            text
        )
    return text

def normalize_hyphenated_streets(text: str) -> str:
    return re.sub(
        r"\b((?:[A-ZÄÖÜa-zäöüß]+-?)+)-(Straße|Weg|Platz|Allee|Ring|Gasse|Damm|Steig|Ufer|Hof|Chaussee)\b",
        lambda m: f"{m.group(1).replace('-', ' ')} {m.group(2)}".replace("  ", " "),
        text
    ).strip()

def normalize_street_names(text: str) -> str:
    """Dodatkowa normalizacja nazw ulic z myślnikami."""
    return re.sub(
        r"(\b[A-ZÄÖÜa-zäöüß]+)-([A-ZÄÖÜa-zäöüß]+)-([A-ZÄÖÜa-zäöüß]+)\s"
        r"(Straße|straße|Weg|Platz|Allee|Ring|Gasse|Damm|Steig|Ufer|Hof|Chaussee)\s\d+",
        r"\1 \2 \3 \4",
        text
    )

# Uniwersalna funkcja detekcji przy użyciu wyrażenia regularnego
def detect_pattern(regex: str, text: str, entity_type: str, score: float) -> list:
    results = []
    # Używamy flagi IGNORECASE, aby wychwycić wszystkie warianty (np. "Straße" i "straße")
    for match in re.finditer(regex, text, flags=re.IGNORECASE):
        logger.debug("Wykryto %s: %s", entity_type, match.group())
        results.append(RecognizerResult(start=match.start(), end=match.end(), entity_type=entity_type, score=score))
    return results

def detect_zip_code(text: str) -> list:
    return detect_pattern(ZIP_CODE_REGEX, text, "ZIP_CODE", 1.0)

def detect_dates(text: str) -> list:
    return detect_pattern(DATE_REGEX, text, "DATE", 1.0)

def detect_credit_cards(text: str) -> list:
    return detect_pattern(CREDIT_CARD_REGEX, text, "CREDIT_CARD", 1.0)

def detect_tax_id(text: str) -> list:
    return detect_pattern(TAX_ID_REGEX, text, "TAX_ID", 1.0)

def detect_phone_numbers(text: str) -> list:
    return detect_pattern(PHONE_NUMBER_REGEX, text, "PHONE_NUMBER", 1.0)

def detect_street(text: str) -> list:
    return detect_pattern(STREET_REGEX, text, "STREET", 1.5)

def detect_license_plates(text: str) -> list:
    return detect_pattern(LICENSE_PLATE_REGEX, text, "LICENSE_PLATE", 1.0)

# Klasa odpowiadająca za proces anonimizacji oraz deanonimizacji
class AnonymizationService:
    def __init__(self):
        self.analyzer = analyzer
        self.anonymizer = anonymizer

    def anonymize_text(self, session_id: str, text: str) -> str:
        """
        Anonimizuje tekst – wykrywa pola zawierające dane wrażliwe, zapisuje ich mapowanie
        w bazie oraz zastępuje oryginalne wartości tokenami.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Normalizacja tekstu przed detekcją
            text = expand_street_abbreviations(text)
            text = preprocess_street_names(text)
            text = normalize_hyphenated_streets(text)
            text = normalize_street_names(text)

            # Detekcja za pomocą funkcji ręcznych
            detected_results = []
            detected_results += detect_zip_code(text)
            detected_results += detect_dates(text)
            detected_results += detect_credit_cards(text)
            detected_results += detect_tax_id(text)
            detected_results += detect_street(text)
            detected_results += detect_phone_numbers(text)
            detected_results += detect_license_plates(text)
            detected_results += detect_names(text)  # Dodajemy bezpośrednią detekcję imion

            # Detekcja przy użyciu silnika NLP
            detected_results += self.analyzer.analyze(text=text, language="de")

            # Mapowanie wykrytych encji na tokeny anonimowe.
            # Używamy krotki (fragment, typ) jako klucza, aby rozróżnić te same frazy różnych typów.
            entity_mapping = {}
            for res in detected_results:
                extracted_text = text[res.start:res.end]
                if is_ignored(extracted_text):
                    continue
                key = (extracted_text, res.entity_type)
                if key not in entity_mapping:
                    anon_token = f"anno_{uuid.uuid4().hex[:8]}"
                    entity_mapping[key] = anon_token
                    cursor.execute(
                        "INSERT INTO anonymization (session_id, anon_id, original_value, entity_type) VALUES (%s, %s, %s, %s)",
                        (session_id, anon_token, extracted_text, res.entity_type)
                    )
                    conn.commit()

            # Zamiana wykrytych fragmentów na tokeny – sortujemy po długości oryginalnego tekstu, by uniknąć konfliktów.
            for (original_text, _), anon_token in sorted(entity_mapping.items(), key=lambda x: len(x[0][0]), reverse=True):
                pattern = re.escape(original_text)
                text = re.sub(pattern, anon_token, text)
            return text

        except Exception as e:
            logger.error("Błąd podczas anonimizacji: %s", e)
            raise
        finally:
            cursor.close()
            conn.close()

    def deanonymize_text(self, session_id: str, text: str) -> str:
        """
        Przywraca oryginalny tekst na podstawie danych zapisanych w bazie (odwrotność anonimizacji).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT anon_id, original_value FROM anonymization WHERE session_id = %s",
                (session_id,)
            )
            mappings = cursor.fetchall()
            for anon_id, original_value in mappings:
                text = re.sub(rf"\b{re.escape(anon_id)}\b", original_value, text)
            return text
        except Exception as e:
            logger.error("Błąd podczas deanonimizacji: %s", e)
            raise
        finally:
            cursor.close()
            conn.close()

# Przykładowe użycie (do testów lokalnych)
if __name__ == "__main__":
    service = AnonymizationService()
    test_session = str(uuid.uuid4())
    sample_text = (
        "Beispieltext mit Hauptstraße 123, 12345, 01. Januar 2020, "
        "+491701234567, 123/456/78901, Werner-von-Siemens-Straße 1, "
        "M AB 123, HH AB 1234."
    )
    logger.info("Oryginalny tekst: %s", sample_text)
    anonymized = service.anonymize_text(test_session, sample_text)
    logger.info("Tekst po anonimizacji: %s", anonymized)
    deanonymized = service.deanonymize_text(test_session, anonymized)
    logger.info("Tekst po deanonimizacji: %s", deanonymized)

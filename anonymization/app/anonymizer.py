import os
import re
import uuid
import psycopg2
import logging
import os
from presidio_analyzer import AnalyzerEngine, RecognizerResult, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import json
import datetime

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

# Lista słów, które nie powinny być anonimizowane
STOP_WORDS = [
    "Strategie", "zufrieden", "Statement", "Spielfeld", "Ergebnis",
    "erfolgreichste", "beste", "neue", "alte", "große", "kleine",
    "wichtige", "interessante", "aktuelle", "zukünftige", "vergangene",
    "politische", "wirtschaftliche", "soziale", "kulturelle", "wissenschaftliche",
    "technische", "medizinische", "rechtliche", "finanzielle", "sportliche",
    "Lieferant", "Patient", "Zeuge", "Firma", "Restaurant", "Hotel", "Geschäft",
    "Konferenz", "Ausstellung", "Konzert", "Demonstration", "Veranstaltung", "Treffen",
    "Ecke", "Adresse", "Paket", "Ware", "Filiale", "Unfall", "Tatort"
]

def is_ignored(text: str) -> bool:
    """Sprawdza, czy dany fragment powinien być pominięty przy anonimizacji."""
    return text.lower() in IGNORED_PHRASES or text in STOP_WORDS

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

# Rozszerzony regex dla dat - obsługuje różne formaty niemieckie, w tym bez kropki po dniu
DATE_REGEX = (
    # Formaty z pełnymi nazwami miesięcy, z kropką i bez kropki po dniu
    r"\b\d{1,2}\.?\s(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s\d{4}\b"
    # Formaty ze skróconymi nazwami miesięcy
    r"|\b\d{1,2}\.?\s(?:Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Sept|Okt|Nov|Dez)\.?\s\d{4}\b"
    # Standardowe formaty numeryczne
    r"|\b\d{1,2}[-\.]\d{1,2}[-\.]\d{2,4}\b"
    r"|\b\d{4}[-\.]\d{1,2}[-\.]\d{1,2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    # Format z tekstowym miesiącem i skrótem roku
    r"|\b\d{1,2}\.?\s(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s\'\d{2}\b"
    r"|\b\d{1,2}\.?\s(?:Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Sept|Okt|Nov|Dez)\.?\s\'\d{2}\b"
    # Format bez kropki po dniu z pełną nazwą miesiąca: "15 Januar 1910"
    r"|\b(\d{1,2})\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b"
    # Format ze skróconymi nazwami miesięcy bez kropki: "15 Jan 1910"
    r"|\b(\d{1,2})\s+(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\s+(\d{4})\b"
)

# Ulepszony regex dla nazw ulic – teraz dopuszcza opcjonalną spację między nazwą a przyrostkiem
STREET_REGEX = (
    r"(?<!\w)(?:[A-ZÄÖÜa-zäöüß]+(?:[-][A-ZÄÖÜa-zäöüß]+)*)(?:\s)?"
    r"(Straße|Weg|Platz|Allee|Ring|Gasse|Damm|Steig|Ufer|Hof|Chaussee)\s\d+(?!\w)"
)

# Regex dla niemieckich tablic rejestracyjnych
LICENSE_PLATE_REGEX = (
    # Format z odstępami: "M AB 123", "B C 1"
    r"\b(?<!\w)([A-ZÄÖÜ]{1,3})\s+([A-ZÄÖÜ]{1,2})\s+(\d{1,4})\b"
    # Format bez spacji: "MAB123", "BC1"
    r"|\b(?<!\w)([A-ZÄÖÜ]{1,3})([A-ZÄÖÜ]{1,2})(\d{1,4})\b"
    # Format z myślnikami: "M-AB-123", "B-C-1"
    r"|\b(?<!\w)([A-ZÄÖÜ]{1,3})-([A-ZÄÖÜ]{1,2})-(\d{1,4})\b"
    # Format z kontekstem: "Kennzeichen M AB 123", "Kennzeichen B C 1"
    r"|Kennzeichen\s+([A-ZÄÖÜ]{1,3})\s+([A-ZÄÖÜ]{1,2})\s+(\d{1,4})"
    # Format z kontekstem "Auto mit dem Kennzeichen"
    r"|Auto mit dem Kennzeichen\s+([A-ZÄÖÜ]{1,3})\s+([A-ZÄÖÜ]{1,2})\s+(\d{1,4})"
    # Format z kontekstem "Wagen"
    r"|Wagen\s+([A-ZÄÖÜ]{1,3})\s+([A-ZÄÖÜ]{1,2})\s+(\d{1,4})"
)

# Regex dla IBAN (International Bank Account Number)
IBAN_REGEX = r"\bDE\d{2}[\s]?(?:\d{4}[\s]?){4,5}\d{0,2}\b"

# Regex dla niemieckich numerów ubezpieczenia społecznego (Sozialversicherungsnummer)
SOCIAL_SECURITY_REGEX = r"\b(\d{2})\s+(\d{6})\s+([A-Z]\d{3})\b"

# Regex dla numerów dowodów osobistych i paszportów
ID_CARD_REGEX = (
    # Niemieckie numery dowodów osobistych (format: L00X00000)
    r"\b[A-Z]\d{2}[A-Z]\d{5}\b"
    # Niemieckie numery paszportów (format: C01X0006X)
    r"|\b[A-Z]\d{2}[A-Z]\d{4}[A-Z]\b"
    # Ogólny format numerów ID
    r"|\b(?:L[A-Z0-9]{8}|T[A-Z0-9]{8}|[0-9]{9}|[A-Z][0-9]{9})\b"
)

# Regex dla rozpoznawania imion zaczynających się na E i kończących na a/e
# Ładowanie listy imion zaczynających się na E i kończących na a/e
def load_german_e_names():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "testfile", "german_e_names.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("names", [])
    except Exception as e:
        logger.error(f"Błąd podczas ładowania listy imion na E: {e}")
        return []

# Lista imion zaczynających się na E i kończących na a/e
GERMAN_E_NAMES = load_german_e_names()

# Tworzenie regex dla imion na E (używane tylko jako fallback, jeśli lista imion jest pusta)
NAME_E_REGEX = r"\b(?<!\w)E[a-zäöüß]{2,6}[ae]\b(?!\w)(?!\s+(?:Straße|Platz|Allee|Berg))"

# Ładowanie listy zawodów z pliku german_real_jobs.json
def load_german_jobs():
    try:
        with open(os.path.join(os.path.dirname(__file__), "data", "german_real_jobs.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("berufe", [])
    except Exception as e:
        logging.error(f"Błąd podczas wczytywania listy zawodów: {e}")
        return []

# Lista zawodów z pliku
GERMAN_JOBS = load_german_jobs()

# Tworzymy regex dla zawodów z pliku
def create_jobs_regex(jobs_list):
    if not jobs_list:
        return r""
    # Sortujemy od najdłuższych do najkrótszych, aby uniknąć częściowych dopasowań
    sorted_jobs = sorted(jobs_list, key=len, reverse=True)
    # Escapujemy znaki specjalne i dodajemy warianty z końcówkami -in dla zawodów żeńskich
    escaped_jobs = []
    for job in sorted_jobs:
        escaped_jobs.append(re.escape(job))
        # Dodajemy wersję żeńską dla zawodów, które mogą ją mieć
        if not job.endswith("in") and not job.endswith("erin") and not job in ["Geologe", "Biologe"]:
            escaped_jobs.append(re.escape(job) + "in")
    
    return r"\b(?:" + "|".join(escaped_jobs) + r")\b"

# Regex dla rozpoznawania pozycji i zawodów
POSITION_REGEX = (
    r"\b(?:CEO|Vorstand(?:svorsitzende[r]?)?|Geschäftsführer(?:in)?|Direktor(?:in)?|Leiter(?:in)?|Manager(?:in)?)\b"
    r"|\b(?:Trainer(?:in)?|Coach|Kapitän(?:in)?|Torwart|Torhüter(?:in)?|Spieler(?:in)?|Staf[f]?el)\b"
    r"|\b(?:Arzt|Ärztin|Chefarzt|Chefärztin|Professor(?:in)?|Dozent(?:in)?|Lehrer(?:in)?)\b"
    r"|\b(?:Anwalt|Anwältin|Richter(?:in)?|Staatsanwalt|Staatsanwältin)\b"
    r"|\b(?:Minister(?:in)?|Kanzler(?:in)?|Präsident(?:in)?|Abgeordnete[r]?|Bürgermeister(?:in)?)\b"
    r"|\b(?:Bundeskanzler(?:in)?|Bundesminister(?:in)?|Botschafter(?:in)?)\b"
)

# Dodajemy zawody z pliku do regexów pozycji
JOBS_REGEX = create_jobs_regex(GERMAN_JOBS)
if JOBS_REGEX:
    POSITION_REGEX = f"{POSITION_REGEX}|{JOBS_REGEX}"

# Tytuły naukowe i medyczne, które będą łączone z imieniem i/lub nazwiskiem
ACADEMIC_TITLES = [
    "Dr", "Dr.", "Doktor", "Prof", "Prof.", "Professor", "Professorin",
    "Priv.-Doz.", "Privatdozent", "Privatdozentin", "PD", "PD.", "P.D.",
    "Dipl.-Ing.", "Diplom-Ingenieur", "Diplom-Ingenieurin",
    "Dipl.-Psych.", "Diplom-Psychologe", "Diplom-Psychologin",
    "Dipl.-Kfm.", "Diplom-Kaufmann", "Diplom-Kauffrau",
    "Dipl.-Vw.", "Diplom-Volkswirt", "Diplom-Volkswirtin",
    "Dipl.-Biol.", "Diplom-Biologe", "Diplom-Biologin",
    "Dipl.-Chem.", "Diplom-Chemiker", "Diplom-Chemikerin",
    "Dipl.-Phys.", "Diplom-Physiker", "Diplom-Physikerin",
    "Dipl.-Math.", "Diplom-Mathematiker", "Diplom-Mathematikerin",
    "Dipl.-Inf.", "Diplom-Informatiker", "Diplom-Informatikerin",
    "M.Sc.", "Master of Science", "M.A.", "Master of Arts",
    "B.Sc.", "Bachelor of Science", "B.A.", "Bachelor of Arts",
    "M.D.", "Medical Doctor", "Ph.D.", "Doctor of Philosophy",
    "M.B.A.", "Master of Business Administration",
    "LL.M.", "Master of Laws", "LL.B.", "Bachelor of Laws",
    "Mag.", "Magister", "Magistra",
    "OA", "OA.", "O.A.", "Oberarzt", "Oberärztin",
    "CA", "CA.", "C.A.", "Chefarzt", "Chefärztin",
    "FA", "FA.", "F.A.", "Facharzt", "Fachärztin",
    "MdB", "MdL", "MdEP", "MEP"
]

# Tworzymy regex dla tytułów naukowych połączonych z imieniem/nazwiskiem
def create_academic_titles_regex(titles_list):
    if not titles_list:
        return r""
    # Sortujemy od najdłuższych do najkrótszych, aby uniknąć częściowych dopasowań
    sorted_titles = sorted(titles_list, key=len, reverse=True)
    # Escapujemy znaki specjalne
    escaped_titles = [re.escape(title) for title in sorted_titles]
    
    # Tworzymy regex, który łączy tytuł z imieniem i/lub nazwiskiem
    # Format: Tytuł + opcjonalnie spacja + opcjonalnie imię + nazwisko
    # lub: Tytuł + spacja + nazwisko
    titles_pattern = "|".join(escaped_titles)
    return (
        # Tytuł + spacja + imię + spacja + nazwisko
        r"\b(?:" + titles_pattern + r")\s+(?:[A-Z][a-zäöüß]+\s+)?[A-Z][a-zäöüß\-]+\b"
        # Tytuł + spacja + nazwisko
        r"|\b(?:" + titles_pattern + r")\s+[A-Z][a-zäöüß\-]+\b"
    )

# Regex dla tytułów naukowych i medycznych połączonych z imieniem/nazwiskiem
ACADEMIC_TITLE_REGEX = create_academic_titles_regex(ACADEMIC_TITLES)

# Regex dla rozpoznawania organizacji
ORGANIZATION_REGEX = (
    r"\b(?:[A-Z][a-zäöüß]+\s)+(?:AG|SE|GmbH|KG|OHG|e\.V\.|GbR|Co\.\sKG)\b"
    r"|\b(?:FC|SV|VfB|VfL|TSV|SC|FSV|Borussia|Bayer|Hertha|Eintracht|Union|Werder|Schalke)\s[A-Z][a-zäöüß]+\b"
    r"|\b(?:Universität|Hochschule|Klinikum|Institut|Ministerium|Bundesamt|Landesamt)\s[A-Z][a-zäöüß]+\b"
)

# Ta lista jest już zdefiniowana na początku pliku
# STOP_WORDS = [
#     "Strategie", "zufrieden", "Statement", "Spielfeld", "Ergebnis",
#     "erfolgreichste", "beste", "neue", "alte", "große", "kleine",
#     "wichtige", "interessante", "aktuelle", "zukünftige", "vergangene",
#     "politische", "wirtschaftliche", "soziale", "kulturelle", "wissenschaftliche",
#     "technische", "medizinische", "rechtliche", "finanzielle", "sportliche"
# ]

# Funkcja filtrująca wyniki z NLP, aby uniknąć duplikacji i fałszywych trafień
def filter_nlp_results(nlp_results, detected_results):
    filtered_results = []
    
    # Najpierw filtrujemy stop words
    filtered_detected = []
    for detected in detected_results:
        # Pobierz tekst encji
        entity_text = detected.entity_type
        
        # Sprawdzamy, czy wykryta encja jest na liście stop words
        if entity_text in STOP_WORDS or is_ignored(entity_text):
            continue
            
        filtered_detected.append(detected)
    
    # Teraz filtrujemy wyniki NLP
    for nlp_result in nlp_results:
        # Pobierz tekst encji
        entity_text = nlp_result.entity_type
        
        # Sprawdzamy, czy encja z NLP jest na liście stop words
        if entity_text in STOP_WORDS or is_ignored(entity_text):
            continue
        
        # Dodajemy wynik do przefiltrowanych
        filtered_results.append(nlp_result)
            
        # Sprawdzamy, czy encja z NLP nie pokrywa się z już wykrytymi encjami
        overlapping = False
        for detected in filtered_detected:
            # Jeśli encje się pokrywają, sprawdzamy priorytety
            if (nlp_result.start <= detected.end and nlp_result.end >= detected.start):
                overlapping = True
                # Jeśli encja z NLP jest dłuższa lub ma wyższy priorytet, zastępujemy
                if ((nlp_result.end - nlp_result.start) > (detected.end - detected.start) or
                        nlp_result.score > detected.score):
                    filtered_detected.remove(detected)
                    overlapping = False
                break
        
        if not overlapping:
            filtered_results.append(nlp_result)
    
    return filtered_results + filtered_detected

# Rejestracja własnych detektorów w analizatorze Presidio
def register_custom_recognizers():
    # Telefon
    phone_pattern = Pattern(name="phone_number", regex=PHONE_NUMBER_REGEX, score=0.7)
    phone_recognizer = PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[phone_pattern])
    analyzer.registry.add_recognizer(phone_recognizer)

    # Numer identyfikacji podatkowej
    tax_id_pattern = Pattern(name="tax_id", regex=TAX_ID_REGEX, score=0.6)
    tax_id_recognizer = PatternRecognizer(supported_entity="TAX_ID", patterns=[tax_id_pattern])
    analyzer.registry.add_recognizer(tax_id_recognizer)

    # Numer karty kredytowej
    credit_card_pattern = Pattern(name="credit_card", regex=CREDIT_CARD_REGEX, score=0.5)
    credit_card_recognizer = PatternRecognizer(supported_entity="CREDIT_CARD", patterns=[credit_card_pattern])
    analyzer.registry.add_recognizer(credit_card_recognizer)

    # Kod pocztowy
    zip_pattern = Pattern(name="zip_code", regex=ZIP_CODE_REGEX, score=0.6)
    zip_recognizer = PatternRecognizer(supported_entity="ZIP", patterns=[zip_pattern])
    analyzer.registry.add_recognizer(zip_recognizer)

    # Data
    date_pattern = Pattern(name="date", regex=DATE_REGEX, score=0.6)
    date_recognizer = PatternRecognizer(supported_entity="DATE", patterns=[date_pattern])
    analyzer.registry.add_recognizer(date_recognizer)
    
    # Imiona zaczynające się na E i kończące na a/e
    if GERMAN_E_NAMES:
        # Jeśli mamy listę imion, tworzymy regex z tej listy
        escaped_names = [re.escape(name) for name in GERMAN_E_NAMES]
        names_pattern = "|".join(escaped_names)
        name_e_regex = r"\b(?:" + names_pattern + r")\b"
        name_e_pattern = Pattern(name="name_e", regex=name_e_regex, score=0.8)
    else:
        # Fallback do oryginalnego regex, jeśli lista jest pusta
        name_e_pattern = Pattern(name="name_e", regex=NAME_E_REGEX, score=0.6)
    
    name_e_recognizer = PatternRecognizer(supported_entity="NAME_E", patterns=[name_e_pattern])
    analyzer.registry.add_recognizer(name_e_recognizer)
    
    # Ulice
    street_pattern = Pattern(name="street", regex=STREET_REGEX, score=0.7)
    street_recognizer = PatternRecognizer(supported_entity="STREET", patterns=[street_pattern])
    analyzer.registry.add_recognizer(street_recognizer)
    
    # Adresy - bardziej kompleksowe wzorce
    address_patterns = [
        # Ulica + numer + kod pocztowy + miasto (pełny adres)
        Pattern(
            name="german_full_address",
            regex=r"([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*(?:[-]?(?:stra(?:ße|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))\s+\d+[a-z]?)\s*,\s*(\d{5})\s+([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)",
            score=0.95,
        ),
        # Ulica + numer + miasto (bez kodu pocztowego)
        Pattern(
            name="german_address_no_zip",
            regex=r"([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*(?:[-]?(?:stra(?:ße|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))\s+\d+[a-z]?)\s*,\s*([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)",
            score=0.85,
        ),
        # Kod pocztowy + miasto
        Pattern(
            name="german_zip_city",
            regex=r"(\d{5})\s+([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)",
            score=0.8,
        ),
        # Ulica z przyimkiem "in der" + kod pocztowy + miasto
        Pattern(
            name="german_address_with_in_der",
            regex=r"in\s+der\s+([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*(?:[-]?(?:stra(?:ße|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))\s+\d+[a-z]?)(?:\s*,\s*(\d{5})\s+([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)?)?",
            score=0.9,
        ),
        # Ulica ze słowem "Straße" + kod pocztowy + miasto
    ]
    # Rejestrujemy nowy typ encji ADDRESS z wzorcami
    address_recognizer = PatternRecognizer(
        supported_entity="ADDRESS",
        patterns=address_patterns,
        context=["adresse", "wohnt", "straße", "platz", "allee", "wohnhaft", "geschickt", "lieferung", "paket", "brief", "in", "nach", "bei"]
    )
    analyzer.registry.add_recognizer(address_recognizer)
    
    # Daty w różnych formatach niemieckich
    # Format bez kropki po dniu: "15 Januar 1910"
    date_no_dot_pattern = Pattern(
        name="german_date_no_dot",
        regex=r"\b(\d{1,2})\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b",
        score=0.99
    )
    # Format ze skróconymi nazwami miesięcy: "15 Jan 1910"
    date_short_month_pattern = Pattern(
        name="german_date_short_month",
        regex=r"\b(\d{1,2})\s+(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\s+(\d{4})\b",
        score=0.99
    )
    # Ogólny wzorzec dla dat
    date_pattern = Pattern(name="date", regex=DATE_REGEX, score=0.95)
    
    date_recognizer = PatternRecognizer(
        supported_entity="DATE_TIME", 
        patterns=[date_no_dot_pattern, date_short_month_pattern, date_pattern]
    )
    analyzer.registry.add_recognizer(date_recognizer)
    
    # Tablice rejestracyjne w różnych formatach
    # Format z odstępami: "M AB 123", "B C 1"
    license_plate_spaces_pattern = Pattern(
        name="german_license_plate_spaces",
        regex=r"\b([A-Z]{1,3})\s+([A-Z]{1,2})\s+(\d{1,4})\b",
        score=0.99
    )
    # Format bez odstępów: "MAB123", "BC1"
    license_plate_no_spaces_pattern = Pattern(
        name="german_license_plate_no_spaces",
        regex=r"\b([A-Z]{1,3})([A-Z]{1,2})(\d{1,4})\b",
        score=0.99
    )
    # Format z myślnikami: "M-AB-123", "B-C-1"
    license_plate_hyphens_pattern = Pattern(
        name="german_license_plate_hyphens",
        regex=r"\b([A-Z]{1,3})-([A-Z]{1,2})-(\d{1,4})\b",
        score=0.99
    )
    # Ogólny wzorzec dla tablic rejestracyjnych
    license_plate_pattern = Pattern(name="license_plate", regex=LICENSE_PLATE_REGEX, score=0.95)
    
    license_plate_recognizer = PatternRecognizer(
        supported_entity="LICENSE_PLATE", 
        patterns=[license_plate_spaces_pattern, license_plate_no_spaces_pattern, license_plate_hyphens_pattern, license_plate_pattern]
    )
    analyzer.registry.add_recognizer(license_plate_recognizer)

    # IBAN
    iban_pattern = Pattern(name="iban", regex=IBAN_REGEX, score=0.95)
    iban_recognizer = PatternRecognizer(supported_entity="IBAN_CODE", patterns=[iban_pattern])
    analyzer.registry.add_recognizer(iban_recognizer)

    # Numer ubezpieczenia społecznego
    social_security_pattern = Pattern(name="social_security", regex=SOCIAL_SECURITY_REGEX, score=0.95)
    social_security_recognizer = PatternRecognizer(supported_entity="SOCIAL_SECURITY", patterns=[social_security_pattern])
    analyzer.registry.add_recognizer(social_security_recognizer)

    # Dowód osobisty / paszport
    id_card_pattern = Pattern(name="id_card", regex=ID_CARD_REGEX, score=0.95)
    id_card_recognizer = PatternRecognizer(supported_entity="ID", patterns=[id_card_pattern])
    analyzer.registry.add_recognizer(id_card_recognizer)

    # Imiona zaczynające się na E i kończące na a/e
    name_e_pattern = Pattern(name="name_e", regex=NAME_E_REGEX, score=0.85)
    name_e_recognizer = PatternRecognizer(supported_entity="PERSON", patterns=[name_e_pattern])
    analyzer.registry.add_recognizer(name_e_recognizer)

    # Pozycja / stanowisko
    position_pattern = Pattern(name="position", regex=POSITION_REGEX, score=0.85)
    position_recognizer = PatternRecognizer(supported_entity="POSITION", patterns=[position_pattern])
    analyzer.registry.add_recognizer(position_recognizer)

    # Organizacja
    organization_pattern = Pattern(name="organization", regex=ORGANIZATION_REGEX, score=0.85)
    organization_recognizer = PatternRecognizer(supported_entity="ORGANIZATION", patterns=[organization_pattern])
    analyzer.registry.add_recognizer(organization_recognizer)

    # Tytuł naukowy z imieniem/nazwiskiem
    academic_title_pattern = Pattern(name="academic_title", regex=ACADEMIC_TITLE_REGEX, score=0.95)
    academic_title_recognizer = PatternRecognizer(supported_entity="PERSON", patterns=[academic_title_pattern])
    analyzer.registry.add_recognizer(academic_title_recognizer)

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
    Identyfikuje złożone nazwy ulic, np. 'Hauptstraße', ale nie modyfikuje
    nazw zawierających myślnik tuż przed przyrostkiem (np. 'Werner-von-Siemens-Straße').
    Zwraca oryginalny tekst, aby zachować oryginalne nazwy ulic w wynikach anonimizacji.
    """
    # W tej wersji funkcji nie modyfikujemy tekstu, aby zachować oryginalne nazwy ulic
    # Funkcja jest zachowana dla kompatybilności z istniejącym kodem
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

def detect_iban(text: str) -> list:
    return detect_pattern(IBAN_REGEX, text, "IBAN", 1.0)

def detect_social_security(text: str) -> list:
    return detect_pattern(SOCIAL_SECURITY_REGEX, text, "SOCIAL_SECURITY", 1.0)

def detect_id_card(text: str) -> list:
    return detect_pattern(ID_CARD_REGEX, text, "ID_CARD", 1.0)

def detect_name_e(text: str) -> list:
    return detect_pattern(NAME_E_REGEX, text, "NAME_E", 0.7)

def detect_position(text: str) -> list:
    return detect_pattern(POSITION_REGEX, text, "POSITION", 0.8)

def detect_organization(text: str) -> list:
    return detect_pattern(ORGANIZATION_REGEX, text, "ORGANIZATION", 0.9)

def detect_academic_title(text: str) -> list:
    return detect_pattern(ACADEMIC_TITLE_REGEX, text, "ACADEMIC_TITLE", 0.9)

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
            detected_results += detect_iban(text)
            detected_results += detect_social_security(text)
            detected_results += detect_id_card(text)
            detected_results += detect_name_e(text)
            detected_results += detect_position(text)
            detected_results += detect_organization(text)
            detected_results += detect_academic_title(text)

            # Detekcja przy użyciu silnika NLP
            nlp_results = self.analyzer.analyze(text=text, language="de")
            
            # Filtrowanie wyników NLP, aby uniknąć duplikacji i fałszywych pozytywów
            detected_results = filter_nlp_results(nlp_results, detected_results)

            # Mapowanie wykrytych encji na tokeny anonimowe.
            # Używamy krotki (fragment, typ) jako klucza, aby rozróżnić te same frazy różnych typów.
            entity_mapping = {}
            
            # Rozwiązywanie nakładających się encji - preferujemy dłuższe i bardziej specyficzne
            # Najpierw sortujemy po długości (dłuższe encje mają priorytet)
            sorted_results = sorted(detected_results, key=lambda x: (x.end - x.start), reverse=True)
            final_results = []
            
            for res in sorted_results:
                # Sprawdzamy, czy ta encja nie nakłada się z już zaakceptowaną
                overlaps = False
                for accepted in final_results:
                    # Jeśli encje się nakładają
                    if not (res.end <= accepted.start or res.start >= accepted.end):
                        overlaps = True
                        break
                
                if not overlaps:
                    final_results.append(res)
            
            # Sortujemy finalne wyniki według pozycji w tekście, aby zachować naturalną kolejność
            final_results = sorted(final_results, key=lambda x: x.start)
            
            # Teraz używamy tylko nie nakładających się encji
            for res in final_results:
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
                # Sprawdzamy, czy wykryty tekst jest na liście stop words
                if original_text in STOP_WORDS or is_ignored(original_text):
                    continue
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
        "M AB 123, B C 1, Eva und Emma wohnen in München, "
        "DE89 3704 0044 0532 0130 00, 15 Januar 1910, 65 220788 A123"
    )
    logger.info("Oryginalny tekst: %s", sample_text)
    anonymized = service.anonymize_text(test_session, sample_text)
    logger.info("Tekst po anonimizacji: %s", anonymized)
    deanonymized = service.deanonymize_text(test_session, anonymized)
    logger.info("Tekst po deanonimizacji: %s", deanonymized)

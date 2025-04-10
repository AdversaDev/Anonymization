import re
import os
import json
import logging
import re
import sys
import uuid
from presidio_analyzer import AnalyzerEngine, RecognizerResult, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguracja NLP (dla języka niemieckiego)
NLP_CONFIG = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}]
}
nlp_engine = NlpEngineProvider(nlp_configuration=NLP_CONFIG).create_engine()
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["de"])

# Lista fraz, które NIE powinny być anonimizowane
IGNORED_PHRASES = {
    "mein name", "krankenversicherungsnummer", "meine kreditkartennummer",
    "mein iban", "mein code", "ich", "ich wohne", "meine", "mein", "und",
    "in", "der", "am", "ist", "das", "die", "den", "dem", "ein", "eine",
    "meine telefonnummer", "meine steuernummer"
}

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
)

# Ulepszony regex dla nazw ulic – teraz dopuszcza opcjonalną spację między nazwą a przyrostkiem
STREET_REGEX = (
    r"(?<!\w)(?:[A-ZÄÖÜa-zäöüß]+(?:[-][A-ZÄÖÜa-zäöüß]+)*)(?:\s)?"
    r"(Straße|Weg|Platz|Allee|Ring|Gasse|Damm|Steig|Ufer|Hof|Chaussee)\s\d+(?!\w)"
)

# Regex dla niemieckich tablic rejestracyjnych
LICENSE_PLATE_REGEX = (
    # Format: 1-3 litery (kod miasta), spacja, 1-2 litery, spacja, 1-4 cyfry
    r"\b(?<!\w)[A-ZÄÖÜ]{1,3}(?:[-\s])[A-ZÄÖÜ]{1,2}(?:[-\s])\d{1,4}\b"
    # Format bez spacji
    r"|\b(?<!\w)[A-ZÄÖÜ]{1,3}[A-ZÄÖÜ]{1,2}\d{1,4}\b"
)

# Regex dla IBAN (International Bank Account Number)
IBAN_REGEX = r"\bDE\d{2}[\s]?(?:\d{4}[\s]?){4,5}\d{0,2}\b"

# Regex dla niemieckich numerów ubezpieczenia społecznego (Sozialversicherungsnummer)
SOCIAL_SECURITY_REGEX = r"\b\d{2}(?:[\s-]?)(?:0[1-9]|[1-9][0-9])(?:[\s-]?)(?:0[1-9]|[1-9][0-9])(?:[\s-]?)\d{2}(?:[\s-]?)\d{6}\b|\b\d{2}[\s-]?\d{6}[\s-]?[A-Z]\d{3}\b"

# Regex dla niemieckich numerów identyfikacyjnych (Personalausweis, Versichertennummer)
ID_CARD_REGEX = r"\b(?:L[A-Z0-9]{8}|T[A-Z0-9]{8}|[0-9]{9}|[A-Z][0-9]{9})\b"

# Regex dla rozpoznawania imion zaczynających się na E i kończących na a/e
# Bardziej precyzyjny, aby unikać fałszywych trafień dla słów takich jak "erfolgreichste" i "Ecke"
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
    )

# Regex dla tytułów naukowych i medycznych połączonych z imieniem/nazwiskiem
ACADEMIC_TITLE_REGEX = create_academic_titles_regex(ACADEMIC_TITLES)

# Regex dla rozpoznawania ulic
STREET_REGEX = (
    # Standardowe nazwy ulic z numerami
    r"(?:[A-Z][a-zäöüß]+(?:stra(?:\u00dfe|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg)\s+\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)?)" 
    # Nazwy ulic z myślnikami
    r"|(?:[A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)+(?:[-](?:stra(?:\u00dfe|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))\s+\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)?)" 
    # Nazwy ulic z przyimkami (von, zu, an, etc.)
    r"|(?:[A-Z][a-zäöüß]+(?:[-](?:von|zu|an|der|dem|den|am|zum|zur|beim|auf|unter|ober|hinter|vor|im|in)[-])+[A-Z][a-zäöüß]+(?:[-](?:stra(?:\u00dfe|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))?\s+\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)?)" 
    # Specjalne nazwy ulic
    r"|(?:(?:Unter\s+den\s+Linden|Kurfürstendamm|Ku'damm|Kudamm)\s+\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)?)" 
    # Nazwy ulic zaczynające się od "Am", "An der", "Zum", "Zur", "Bei", "Auf'm", "Unter'm", etc.
    r"|(?:(?:Am|An\s+der|An\s+dem|Zum|Zur|Bei|Beim|Auf'm|Unter'm|In\s+der|In\s+dem)\s+[A-Z][a-zäöüß]+(?:\s+[A-Z][a-zäöüß]+)*\s+\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)?)" 
    # Nazwy ulic z datami (np. "Straße des 17. Juni")
    r"|(?:Straße\s+des\s+\d+\.\s+[A-Z][a-zäöüß]+(?:\s+\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)?)?)" 
)

# Regex dla rozpoznawania organizacji
ORGANIZATION_REGEX = (
    r"\b(?:[A-Z][a-zäöüß]+\s)+(?:AG|SE|GmbH|KG|OHG|e\.V\.|GbR|Co\.\sKG)\b"
    r"|\b(?:FC|SV|VfB|VfL|TSV|SC|FSV|Borussia|Bayer|Hertha|Eintracht|Union|Werder|Schalke)\s[A-Z][a-zäöüß]+\b"
    r"|\b(?:Universität|Hochschule|Klinikum|Institut|Ministerium|Bundesamt|Landesamt)\s[A-Z][a-zäöüß]+\b"
)

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
        text = re.sub(abbr, full_form, text)
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
    # Dodatkowa normalizacja dla nazw ulic z myślnikami
    return text

def normalize_street_names(text: str) -> str:
    """Dodatkowa normalizacja nazw ulic z myślnikami."""
    return text

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

# Rejestracja własnych detektorów w analizatorze Presidio
def register_custom_recognizers():
    custom_entities = [
        ("ZIP_CODE", ZIP_CODE_REGEX, 1.0),
        ("DATE", DATE_REGEX, 1.0),
        ("CREDIT_CARD", CREDIT_CARD_REGEX, 1.0),
        ("TAX_ID", TAX_ID_REGEX, 1.0),
        ("PHONE_NUMBER", PHONE_NUMBER_REGEX, 1.0),
        ("STREET", STREET_REGEX, 1.5),
        ("LICENSE_PLATE", LICENSE_PLATE_REGEX, 1.0),
        ("IBAN", IBAN_REGEX, 1.0),
        ("SOCIAL_SECURITY", SOCIAL_SECURITY_REGEX, 1.0),
        ("ID_CARD", ID_CARD_REGEX, 1.0),
        ("NAME_E", NAME_E_REGEX, 0.7),
        ("POSITION", POSITION_REGEX, 0.8),
        ("ORGANIZATION", ORGANIZATION_REGEX, 0.9),
        ("ACADEMIC_TITLE", ACADEMIC_TITLE_REGEX, 0.9),
        ("ADDRESS", r"", 0.0)  # Pusty regex, ponieważ adresy będą tworzone dynamicznie
    ]
    for entity, regex, score in custom_entities:
        pattern = Pattern(name=entity, regex=regex, score=score)
        recognizer = PatternRecognizer(supported_entity=entity, patterns=[pattern])
        analyzer.registry.add_recognizer(recognizer)

def anonymize_with_presidio(text):
    """Anonimizuje tekst za pomocą Presidio Analyzer.
    
    Funkcja wykorzystuje ulepszony system anonimizacji, który obsługuje:
    1. Daty w różnych formatach niemieckich (w tym "15 Januar 1910" bez kropki po dniu)
    2. Niemieckie tablice rejestracyjne (np. "M AB 123", "B C 1")
    3. Imiona zaczynające się na E i kończące na a/e (np. Eva, Emma, Elena)
    4. Numery identyfikacyjne (dowody osobiste, paszporty, ubezpieczenie społeczne)
    
    Args:
        text (str): Tekst do anonimizacji
        
    Returns:
        str: Zanonimizowany tekst
    """
    # Konfiguracja NLP (dla języka niemieckiego)
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}]
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["de"])
    
    # Rejestracja własnych recognizerów
    register_custom_recognizers(analyzer)
    
    # Analiza tekstu
    results = analyzer.analyze(text=text, language="de")
    
    # Dodatkowe wykrywanie dat i tablic rejestracyjnych, które nie są wykrywane przez Presidio
    additional_entities = []
    
    # Wykrywanie dat w formatach niemieckich bez kropek
    date_patterns = [
        # Format bez kropki po dniu: "15 Januar 1910"
        (r"\b(\d{1,2})\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b", "DATE_TIME"),
        # Format ze skróconymi nazwami miesięcy: "15 Jan 1910"
        (r"\b(\d{1,2})\s+(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\s+(\d{4})\b", "DATE_TIME")
    ]
    
    # Wykrywanie niemieckich tablic rejestracyjnych
    license_plate_patterns = [
        # Format z odstępami: "M AB 123", "B C 1"
        (r"\b([A-Z]{1,3})\s+([A-Z]{1,2})\s+(\d{1,4})\b", "LICENSE_PLATE"),
        # Format bez odstępów: "MAB123", "BC1"
        (r"\b([A-Z]{1,3})([A-Z]{1,2})(\d{1,4})\b", "LICENSE_PLATE"),
        # Format z myślnikami: "M-AB-123", "B-C-1"
        (r"\b([A-Z]{1,3})-([A-Z]{1,2})-(\d{1,4})\b", "LICENSE_PLATE")
    ]
    
    # Wykrywanie numerów identyfikacyjnych
    id_patterns = [
        # Niemieckie numery ubezpieczenia społecznego (format: XX DDMMYY AXXX)
        (r"\b(\d{2})\s+(\d{6})\s+([A-Z]\d{3})\b", "ID_NUMBER")
    ]
    
    # Łączymy wszystkie wzorce
    all_patterns = date_patterns + license_plate_patterns + id_patterns
    
    # Wyszukujemy dodatkowe encje za pomocą własnych wzorów
    for pattern, entity_type in all_patterns:
        for match in re.finditer(pattern, text):
            start = match.start()
            end = match.end()
            matched_text = match.group()
            
            # Sprawdzamy, czy ta encja nie została już wykryta przez Presidio
            is_overlapping = False
            for result in results:
                if (start >= result.start and start < result.end) or \
                   (end > result.start and end <= result.end) or \
                   (start <= result.start and end >= result.end):
                    is_overlapping = True
                    break
            
            if not is_overlapping:
                additional_entities.append({
                    "start": start,
                    "end": end,
                    "entity_type": entity_type,
                    "text": matched_text
                })
    
    # Generowanie unikalnych tokenów dla każdej encji
    anonymized_results = []
    
    # Dodajemy encje wykryte przez Presidio
    for result in results:
        entity_type = result.entity_type
        # Generujemy unikalny token dla każdej encji
        replacement_text = f"anno_{uuid.uuid4().hex[:8]}"
        anonymized_results.append({
            "start": result.start,
            "end": result.end,
            "entity_type": entity_type,
            "text": text[result.start:result.end],
            "replacement": replacement_text
        })
    
    # Dodajemy encje wykryte przez nasze własne wzorce
    for entity in additional_entities:
        entity_type = entity["entity_type"]
        # Generujemy unikalny token dla każdej encji
        replacement_text = f"anno_{uuid.uuid4().hex[:8]}"
        anonymized_results.append({
            "start": entity["start"],
            "end": entity["end"],
            "entity_type": entity_type,
            "text": entity["text"],
            "replacement": replacement_text
        })
    
    # Sortujemy wyniki według pozycji (od końca tekstu, aby uniknąć przesunięcia indeksów)
    anonymized_results.sort(key=lambda x: x["start"], reverse=True)
    
    # Zamieniamy wykryte fragmenty na tokeny anonimizacyjne
    anonymized_text = text
    for result in anonymized_results:
        start = result["start"]
        end = result["end"]
        replacement = result["replacement"]
        
        # Wypisujemy informacje o wykrytej encji
        logger.info(f"Wykryto {result['entity_type']}: '{result['text']}' -> '{replacement}'")
        
        # Zamieniamy fragment tekstu na token anonimizacyjny
        anonymized_text = anonymized_text[:start] + replacement + anonymized_text[end:]
    
    return anonymized_text

def register_custom_recognizers(analyzer):
    """Rejestruje własne recognizery w Presidio Analyzer.
    
    Funkcja dodaje recognizery dla:
    1. Dat w różnych formatach niemieckich
    2. Niemieckich tablic rejestracyjnych
    3. Imion zaczynających się na E i kończących na a/e
    4. Adresów w różnych formatach
    5. Numerów identyfikacyjnych (dowody osobiste, paszporty, ubezpieczenie społeczne)
    
    Args:
        analyzer (AnalyzerEngine): Instancja Presidio Analyzer
    """
    # Wzorce dla dat w różnych formatach niemieckich
    date_patterns = [
        # Format bez kropki po dniu: "15 Januar 1910"
        Pattern(
            name="german_date_no_dot",
            regex=r"\b(\d{1,2})\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b",
            score=0.99
        ),
        # Format ze skróconymi nazwami miesięcy: "15 Jan 1910"
        Pattern(
            name="german_date_short_month",
            regex=r"\b(\d{1,2})\s+(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\s+(\d{4})\b",
            score=0.99
        ),
        # Format z kropkami: "01.02.2023"
        Pattern(
            name="german_date_dots",
            regex=r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})\b",
            score=0.95
        ),
        # Format z myślnikami: "15-03-2023"
        Pattern(
            name="german_date_hyphens",
            regex=r"\b(\d{1,2})-(\d{1,2})-(\d{4}|\d{2})\b",
            score=0.95
        ),
        # Format ISO: "2023-04-30"
        Pattern(
            name="german_date_iso",
            regex=r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
            score=0.95
        ),
        # Format z miesiącem tekstowym i kropką po dniu: "15. Januar 1910"
        Pattern(
            name="german_date_dot_month",
            regex=r"\b(\d{1,2})\. (Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b",
            score=0.99
        ),
        # Format z miesiącem tekstowym skróconym i kropką po dniu: "15. Jan 1910"
        Pattern(
            name="german_date_dot_short_month",
            regex=r"\b(\d{1,2})\. (Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\s+(\d{4})\b",
            score=0.99
        )
    ]
    
    # Wzorzec dla niemieckich tablic rejestracyjnych
    license_plate_patterns = [
        # Format z odstępami: "M AB 123", "B C 1"
        Pattern(
            name="german_license_plate_spaces",
            regex=r"\b([A-Z]{1,3})\s+([A-Z]{1,2})\s+(\d{1,4})\b",
            score=0.99
        ),
        # Format bez odstępów: "MAB123", "BC1"
        Pattern(
            name="german_license_plate_no_spaces",
            regex=r"\b([A-Z]{1,3})([A-Z]{1,2})(\d{1,4})\b",
            score=0.99
        ),
        # Format z myślnikami: "M-AB-123", "B-C-1"
        Pattern(
            name="german_license_plate_hyphens",
            regex=r"\b([A-Z]{1,3})-([A-Z]{1,2})-(\d{1,4})\b",
            score=0.99
        ),
        # Format z kontekstem: "Kennzeichen M AB 123", "Kennzeichen B C 1"
        Pattern(
            name="german_license_plate_with_context",
            regex=r"Kennzeichen\s+([A-Z]{1,3})\s+([A-Z]{1,2})\s+(\d{1,4})",
            score=0.99
        ),
        # Format z kontekstem i myślnikami: "Kennzeichen M-AB-123", "Kennzeichen B-C-1"
        Pattern(
            name="german_license_plate_with_context_hyphens",
            regex=r"Kennzeichen\s+([A-Z]{1,3})-([A-Z]{1,2})-(\d{1,4})",
            score=0.99
        ),
        # Format z kontekstem "Auto mit dem Kennzeichen"
        Pattern(
            name="german_license_plate_with_auto_context",
            regex=r"Auto mit dem Kennzeichen\s+([A-Z]{1,3})\s+([A-Z]{1,2})\s+(\d{1,4})",
            score=0.99
        ),
        # Format z kontekstem "Wagen"
        Pattern(
            name="german_license_plate_with_wagen_context",
            regex=r"Wagen\s+([A-Z]{1,3})\s+([A-Z]{1,2})\s+(\d{1,4})",
            score=0.99
        ),
        # Format z kontekstem "Wagen" bez odstępów
        Pattern(
            name="german_license_plate_with_wagen_context_no_spaces",
            regex=r"Wagen\s+([A-Z]{1,3})([A-Z]{1,2})(\d{1,4})",
            score=0.99
        ),
        # Format z kontekstem "Auto" bez odstępów
        Pattern(
            name="german_license_plate_with_auto_context_no_spaces",
            regex=r"Auto\s+([A-Z]{1,3})([A-Z]{1,2})(\d{1,4})",
            score=0.99
        )
    ]
    
    # Wzorzec dla imion zaczynających się na E i kończących na a/e
    name_e_pattern = Pattern(
        name="german_name_e_ending_ae",
        regex=r"\b(?<!\w)E[a-zäöüß]{2,6}[ae]\b(?!\w)(?!\s+(?:Straße|Platz|Allee|Berg))",
        score=0.85
    )
    
    # Wzorce dla adresów
    address_patterns = [
        # Ulica + numer + kod pocztowy + miasto
        Pattern(
            name="german_full_address",
            regex=r"([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*(?:[-]?(?:stra(?:ße|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))\s+\d+[a-z]?)\s*,\s*(\d{5})\s+([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)",
            score=0.95
        ),
        # Kod pocztowy + miasto
        Pattern(
            name="german_zip_city",
            regex=r"(\d{5})\s+([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)",
            score=0.9
        ),
        # Ulica + numer
        Pattern(
            name="german_street_number",
            regex=r"([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*(?:[-]?(?:stra(?:ße|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))\s+\d+[a-z]?)",
            score=0.85
        )
    ]
    
    # Wzorce dla numerów identyfikacyjnych
    id_patterns = [
        # Niemieckie numery ubezpieczenia społecznego (format: XX DDMMYY AXXX)
        Pattern(
            name="german_social_security",
            regex=r"\b(\d{2})\s+(\d{6})\s+([A-Z]\d{3})\b",
            score=0.95
        ),
        # Niemieckie numery dowodów osobistych (format: L00X00000)
        Pattern(
            name="german_id_card",
            regex=r"\b[A-Z]\d{2}[A-Z]\d{5}\b",
            score=0.95
        ),
        # Niemieckie numery paszportów (format: C01X0006X)
        Pattern(
            name="german_passport",
            regex=r"\b[A-Z]\d{2}[A-Z]\d{4}[A-Z]\b",
            score=0.95
        ),
        # Ogólny format numerów ID
        Pattern(
            name="general_id_number",
            regex=r"\b[A-Z]\d+\b",
            score=0.7
        )
    ]
    
    # Rejestracja recognizerów
    # 1. Recognizer dla dat
    date_recognizer = PatternRecognizer(
        supported_entity="DATE_TIME",
        patterns=date_patterns
    )
    analyzer.registry.add_recognizer(date_recognizer)
    
    # 2. Recognizer dla tablic rejestracyjnych
    license_plate_recognizer = PatternRecognizer(
        supported_entity="LICENSE_PLATE",
        patterns=license_plate_patterns
    )
    analyzer.registry.add_recognizer(license_plate_recognizer)
    
    # 3. Recognizer dla imion zaczynających się na E
    name_e_recognizer = PatternRecognizer(
        supported_entity="PERSON",
        patterns=[name_e_pattern]
    )
    analyzer.registry.add_recognizer(name_e_recognizer)
    
    # 4. Recognizer dla adresów
    address_recognizer = PatternRecognizer(
        supported_entity="ADDRESS",
        patterns=address_patterns
    )
    analyzer.registry.add_recognizer(address_recognizer)
    
    # 5. Recognizer dla numerów identyfikacyjnych
    id_recognizer = PatternRecognizer(
        supported_entity="ID_NUMBER",
        patterns=id_patterns
    )
    analyzer.registry.add_recognizer(id_recognizer)

class SimpleAnonymizer:
    """
    Uproszczona wersja anonymizera bez konieczności połączenia z bazą danych.
    Używa prostych tokenów do anonimizacji, bez możliwości deanonimizacji.
    """
    def __init__(self):
        self.analyzer = analyzer
    
    def anonymize_text(self, text: str) -> str:
        """
        Anonimizuje tekst - wykrywa pola zawierające dane wrażliwe i zastępuje je tokenami.
        Nie zapisuje mapowania, więc nie ma możliwości deanonimizacji.
        """
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
            
            # Filtrujemy wyniki NLP, aby uniknąć duplikacji i fałszywych trafień
            filtered_results = []
            
            # Najpierw filtrujemy stop words
            filtered_detected = []
            for detected in detected_results:
                is_stop_word = False
                for stop_word in STOP_WORDS:
                    if detected.entity_type != "PERSON" and detected.entity_type != "ORGANIZATION":
                        # Sprawdzamy, czy wykryta encja jest na liście stop words
                        if stop_word.lower() in detected.entity_type.lower():
                            is_stop_word = True
                            break
                if not is_stop_word:
                    filtered_detected.append(detected)
            
            # Teraz filtrujemy wyniki NLP
            for nlp_result in nlp_results:
                # Sprawdzamy, czy encja z NLP nie jest stop word
                is_stop_word = False
                for stop_word in STOP_WORDS:
                    if nlp_result.entity_type != "PERSON" and nlp_result.entity_type != "ORGANIZATION":
                        if stop_word.lower() in nlp_result.entity_type.lower():
                            is_stop_word = True
                            break
                
                if is_stop_word:
                    continue
                    
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
            
            detected_results = filtered_results + filtered_detected

            # Mapowanie wykrytych encji na tokeny anonimowe
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
            
            # Prostsze podejście do łączenia adresów - bezpośrednio modyfikujemy tekst
            # Najpierw identyfikujemy wszystkie możliwe wzorce adresów w tekście
            address_patterns = [
                # Ulica + kod pocztowy + miasto
                r"([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*(?:[-]?(?:stra(?:ße|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))\s+\d+(?:[a-z])?)\s*,\s*(\d{5})\s+([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)",
                # Ulica + miasto (bez kodu pocztowego)
                r"([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*(?:[-]?(?:stra(?:ße|sse)|allee|platz|markt|ring|weg|ufer|damm|gasse|park|berg))\s+\d+(?:[a-z])?)\s*,\s*([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)",
                # Kod pocztowy + miasto
                r"(\d{5})\s+([A-Z][a-zäöüß]+(?:[-][A-Z][a-zäöüß]+)*)"
            ]
            
            # Szukamy adresów w tekście
            address_matches = []
            for pattern in address_patterns:
                for match in re.finditer(pattern, text):
                    address_matches.append((match.start(), match.end(), match.group(0)))
            
            # Sortujemy znalezione adresy według pozycji w tekście (od najdłuższych do najkrótszych)
            address_matches.sort(key=lambda x: (-len(x[2]), x[0]))
            
            # Tworzymy encje dla znalezionych adresów
            address_entities = []
            for start, end, address_text in address_matches:
                # Sprawdzamy, czy ten adres nie nakłada się z już znalezionymi
                overlaps = False
                for entity in address_entities:
                    if not (end <= entity.start or start >= entity.end):
                        overlaps = True
                        break
                
                if not overlaps:
                    # Tworzymy nową encję dla adresu
                    address_entity = RecognizerResult(
                        entity_type="ADDRESS",
                        start=start,
                        end=end,
                        score=0.95
                    )
                    address_entities.append(address_entity)
            
            # Filtrujemy wyniki, usuwając elementy adresu, które są częścią większych adresów
            filtered_results = []
            for res in final_results:
                # Sprawdzamy, czy element jest częścią jakiegoś adresu
                is_part_of_address = False
                if res.entity_type in ["STREET", "ZIP", "LOCATION"]:
                    for addr_entity in address_entities:
                        if res.start >= addr_entity.start and res.end <= addr_entity.end:
                            is_part_of_address = True
                            break
                
                if not is_part_of_address:
                    filtered_results.append(res)
            
            # Dodajemy encje adresów do wyników
            filtered_results.extend(address_entities)
            
            # Sortujemy wyniki według pozycji w tekście
            grouped_results = sorted(filtered_results, key=lambda x: x.start)
            
            # Teraz używamy pogrupowanych wyników
            for res in grouped_results:
                extracted_text = text[res.start:res.end]
                # Sprawdzamy, czy tekst jest na liście stop words lub powinien być pominięty
                if extracted_text in STOP_WORDS or is_ignored(extracted_text):
                    continue
                
                # Używamy typu encji jako podstawy do generowania tokenów
                entity_type = res.entity_type
                if (extracted_text, entity_type) not in entity_mapping:
                    # Generujemy token w formacie anno_xxxxx, zgodny z głównym systemem
                    import hashlib
                    # Tworzymy hash z tekstu i typu encji, aby zapewnić spójność tokenów
                    hash_obj = hashlib.md5(f"{extracted_text}_{entity_type}".encode())
                    hash_hex = hash_obj.hexdigest()[:8]  # Bierzemy pierwsze 8 znaków hasha
                    anon_token = f"anno_{hash_hex}"
                    entity_mapping[(extracted_text, entity_type)] = anon_token
                    
                    # Logowanie wykrytych encji
                    logger.info(f"Wykryto {entity_type}: '{extracted_text}' -> '{anon_token}'")

            # Zamiana wykrytych fragmentów na tokeny - sortujemy po długości oryginalnego tekstu, by uniknąć konfliktów
            for (original_text, _), anon_token in sorted(entity_mapping.items(), key=lambda x: len(x[0][0]), reverse=True):
                pattern = re.escape(original_text)
                text = re.sub(pattern, anon_token, text)
                
            return text

        except Exception as e:
            logger.error("Błąd podczas anonimizacji: %s", e)
            raise

def test_anonymization(text: str):
    """Funkcja testowa do anonimizacji tekstu bez konieczności połączenia z bazą danych."""
    anonymizer = SimpleAnonymizer()
    
    print("\nOryginalny tekst:")
    print(text)
    logger.info("Oryginalny tekst:")
    logger.info(text)
    
    anonymized = anonymizer.anonymize_text(text)
    
    print("\nTekst po anonimizacji:")
    print(anonymized)
    logger.info("\nTekst po anonimizacji:")
    logger.info(anonymized)
    
    return anonymized

def save_test_results_to_file(results):
    """Zapisuje wyniki testów do pliku tekstowego"""
    with open("test_results_detailed.txt", "w", encoding="utf-8") as f:
        for result in results:
            f.write(result + "\n")

def load_test_sentences(test_file="extended_test_cases.json"):
    """Wczytuje zdania testowe z podanego pliku JSON
    
    Args:
        test_file (str): Nazwa pliku testowego (domyślnie: extended_test_cases.json)
    
    Returns:
        list: Lista zdań testowych
    """
    try:
        with open(f"testfile/{test_file}", "r", encoding="utf-8") as f:
            data = json.load(f)
            # Zwracamy tylko teksty z przypadków testowych
            return [case["text"] for case in data["test_cases"]]
    except Exception as e:
        logger.error(f"Błąd podczas wczytywania pliku {test_file}: {e}")
        # Spróbujmy wczytać inne pliki testowe jako zapasowe
        backup_files = ["comprehensive_test_cases.json", "address_test.json"]
        for backup_file in backup_files:
            if backup_file != test_file:
                try:
                    with open(f"testfile/{backup_file}", "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "test_cases" in data:
                            return [case["text"] for case in data["test_cases"]]
                        elif "sentences" in data:
                            return data["sentences"]
                except Exception as e2:
                    logger.error(f"Błąd podczas wczytywania pliku zapasowego {backup_file}: {e2}")
        # Jeśli żaden plik nie zadziałał, zwróć pustą listę
        return []

if __name__ == "__main__":
    # Sprawdź, czy podano argument z nazwą pliku testowego
    test_file = "extended_test_cases.json"  # Domyślny plik testowy
    
    # Jeśli podano argument wiersza poleceń, użyj go jako nazwy pliku testowego
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    
    # Wczytaj zdania testowe z podanego pliku
    test_sentences = load_test_sentences(test_file)
    
    if not test_sentences:
        logger.error("Brak zdań testowych do anonimizacji.")
        sys.exit(1)
    
    logger.info(f"Liczba zdań testowych do anonimizacji: {len(test_sentences)}")
    
    # Utwórz nazwę pliku wynikowego na podstawie nazwy pliku testowego
    result_file = f"test_results_{test_file.replace('.json', '')}.txt"
    
    # Otwórz plik do zapisywania wyników
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(f"WYNIKI TESTÓW ANONIMIZACJI - {test_file}\n")
        f.write("=" * 50 + "\n\n")
        
        # Iteruj przez zdania testowe
        for i, text in enumerate(test_sentences, 1):
            f.write(f"===== TEST {i}/{len(test_sentences)} =====\n")
            f.write("Oryginalny tekst:\n")
            f.write(text + "\n\n")
            
            # Anonimizuj tekst
            anonymized_text = anonymize_with_presidio(text)
            
            f.write("Tekst po anonimizacji:\n")
            f.write(anonymized_text + "\n\n\n")
    
    logger.info(f"Testy zakończone. Przetestowano {len(test_sentences)} zdań.")
    logger.info(f"Szczegółowe wyniki zapisano w pliku '{result_file}'.")  

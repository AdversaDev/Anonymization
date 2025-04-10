import os
import sys
import json
import logging
import re
import uuid
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Dodajemy ścieżkę do katalogu nadrzędnego, aby móc importować moduły
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importujemy moduł anonymizer dla wzorów adresów
from app.anonymizer import register_custom_recognizers

# Konfiguracja loggera
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_test_addresses():
    """Wczytuje zdania testowe z pliku address_test.json"""
    try:
        with open("testfile/address_test.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["sentences"]
    except Exception as e:
        logger.error(f"Błąd podczas wczytywania pliku address_test.json: {e}")
        return []

def simple_anonymize_text(text):
    """Prosta funkcja anonimizująca tekst bez użycia bazy danych"""
    # Konfiguracja NLP (dla języka niemieckiego)
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}]
    }
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["de"])
    
    # Rejestrujemy własne rozpoznawacze
    registry = analyzer.registry
    register_custom_recognizers()
    
    # Analizujemy tekst
    results = analyzer.analyze(text=text, language="de")
    
    # Tworzymy słownik mapowań dla wykrytych encji
    entity_mapping = {}
    
    # Sortujemy wyniki według długości, aby uniknąć nakładania się encji
    sorted_results = sorted(results, key=lambda x: (x.end - x.start), reverse=True)
    final_results = []
    
    # Filtrujemy nakładające się encje
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
    
    # Sortujemy finalne wyniki według pozycji w tekście
    final_results = sorted(final_results, key=lambda x: x.start)
    
    # Tworzymy kopię tekstu do anonimizacji
    anonymized_text = text
    
    # Dla każdej wykrytej encji generujemy token anonimizacyjny
    for res in final_results:
        entity_text = text[res.start:res.end]
        entity_type = res.entity_type
        
        # Generujemy unikalny token dla każdej encji
        anon_token = f"anno_{uuid.uuid4().hex[:8]}"
        entity_mapping[(entity_text, entity_type)] = anon_token
        
        # Zapisujemy informacje o wykrytej encji
        logger.info(f"Wykryto {entity_type}: '{entity_text}' -> '{anon_token}'")
    
    # Zamieniamy wykryte fragmenty na tokeny - sortujemy po długości oryginalnego tekstu
    for (original_text, _), anon_token in sorted(entity_mapping.items(), key=lambda x: len(x[0][0]), reverse=True):
        pattern = re.escape(original_text)
        anonymized_text = re.sub(pattern, anon_token, anonymized_text)
    
    return anonymized_text, final_results

def test_address_anonymization():
    """Test anonimizacji adresów"""
    # Wczytaj zdania testowe
    test_sentences = load_test_addresses()
    
    if not test_sentences:
        logger.error("Brak zdań testowych do anonimizacji.")
        return
    
    logger.info(f"Liczba zdań testowych do anonimizacji: {len(test_sentences)}")
    
    # Otwórz plik do zapisywania wyników
    with open("address_test_results.txt", "w", encoding="utf-8") as f:
        f.write("WYNIKI TESTÓW ANONIMIZACJI ADRESÓW\n")
        f.write("=" * 50 + "\n\n")
        
        # Iteruj przez zdania testowe
        for i, text in enumerate(test_sentences, 1):
            f.write(f"===== TEST {i}/{len(test_sentences)} =====\n")
            f.write("Oryginalny tekst:\n")
            f.write(text + "\n\n")
            
            # Anonimizuj tekst
            try:
                anonymized_text, detected_entities = simple_anonymize_text(text)
                
                # Zapisz wyniki anonimizacji
                f.write("Wykryte encje:\n")
                for entity in detected_entities:
                    entity_text = text[entity.start:entity.end]
                    f.write(f"- {entity.entity_type}: '{entity_text}'\n")
                
                f.write("\nTekst po anonimizacji:\n")
                f.write(anonymized_text + "\n\n")
            except Exception as e:
                f.write(f"\nBłąd podczas anonimizacji: {e}\n\n")
            
            f.write("-" * 50 + "\n\n")
    
    logger.info(f"Testy zakończone. Przetestowano {len(test_sentences)} zdań.")
    logger.info(f"Szczegółowe wyniki zapisano w pliku 'address_test_results.txt'.")

if __name__ == "__main__":
    test_address_anonymization()

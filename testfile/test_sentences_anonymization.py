import requests
import json
import uuid
import re
import os
import sys
from datetime import datetime

# Funkcja do anonimizacji tekstu
def anonymize_text(text, session_id):
    print(f"Anonimizacja tekstu: {text}")
    response = requests.post(
        "http://localhost:8001/anonymize",
        json={"text": text, "session_id": session_id}
    )
    
    if response.status_code != 200:
        print(f"Błąd podczas anonimizacji: {response.status_code}, {response.text}")
        return None
    
    result = response.json()
    anonymized_text = result.get("anonymized_text")
    
    if not anonymized_text:
        print("Błąd: Brak zanonimizowanego tekstu w odpowiedzi")
        return None
    
    return anonymized_text

# Funkcja do deanonimizacji tekstu
def deanonymize_text(text, session_id):
    print(f"Deanonimizacja tekstu: {text}")
    
    # Wyodrębniamy tokeny z tekstu
    anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
    anno_tokens = anno_pattern.findall(text)
    unique_tokens = sorted(set(anno_tokens))
    
    if not unique_tokens:
        print("Brak tokenów do deanonimizacji")
        return text
    
    print(f"Znaleziono {len(unique_tokens)} unikalnych tokenów")
    
    # Deanonimizujemy każdy token osobno
    token_mapping = {}
    for token in unique_tokens:
        response = requests.post(
            "http://localhost:8001/deanonymize",
            json={"text": token, "session_id": session_id}
        )
        
        if response.status_code != 200:
            print(f"Błąd podczas deanonimizacji tokenu {token}: {response.status_code}, {response.text}")
            token_mapping[token] = token
        else:
            result = response.json()
            deanonymized_token = result.get("deanonymized_text")
            
            if deanonymized_token and deanonymized_token != token:
                token_mapping[token] = deanonymized_token
                print(f"Token {token} zdeanonimizowany do: {deanonymized_token}")
            else:
                token_mapping[token] = token
                print(f"Token {token} nie został zdeanonimizowany")
    
    # Zastępujemy wszystkie tokeny w tekście
    deanonymized_text = text
    for token, original in token_mapping.items():
        pattern = r'\b' + re.escape(token) + r'\b'
        deanonymized_text = re.sub(pattern, original, deanonymized_text)
    
    return deanonymized_text

# Główna funkcja testowa
def test_sentences_anonymization():
    # Wczytujemy zdania testowe
    try:
        with open("test_sentences_de.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            sentences = data.get("test_sentences", [])
    except Exception as e:
        print(f"Błąd podczas wczytywania pliku test_sentences_de.json: {str(e)}")
        return
    
    if not sentences:
        print("Brak zdań testowych")
        return
    
    print(f"Wczytano {len(sentences)} zdań testowych")
    
    # Generujemy unikalny session_id
    session_id = str(uuid.uuid4())
    print(f"Używam session_id: {session_id}")
    
    # Przygotowujemy plik wynikowy
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"test_sentences_results_{timestamp}.txt"
    
    # Testujemy anonimizację i deanonimizację dla każdego zdania
    with open(results_file, "w", encoding="utf-8") as f:
        f.write(f"Test anonimizacji i deanonimizacji zdań - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Session ID: {session_id}\n\n")
        
        for i, sentence in enumerate(sentences):
            print(f"\nTestowanie zdania {i+1}/{len(sentences)}")
            f.write(f"Zdanie {i+1}: {sentence}\n")
            
            # Anonimizacja
            anonymized = anonymize_text(sentence, session_id)
            if not anonymized:
                f.write("Błąd: Nie udało się zanonimizować zdania\n\n")
                continue
            
            f.write(f"Zanonimizowane: {anonymized}\n")
            
            # Deanonimizacja
            deanonymized = deanonymize_text(anonymized, session_id)
            f.write(f"Zdeanonimizowane: {deanonymized}\n")
            
            # Sprawdzenie, czy deanonimizacja była udana
            if deanonymized == sentence:
                f.write("Wynik: SUKCES - Zdeanonimizowany tekst jest identyczny z oryginalnym\n\n")
            else:
                f.write("Wynik: RÓŻNICA - Zdeanonimizowany tekst różni się od oryginalnego\n")
                f.write(f"Różnica: {show_diff(sentence, deanonymized)}\n\n")
    
    print(f"\nTest zakończony. Wyniki zapisane do pliku {results_file}")

# Funkcja pomocnicza do pokazywania różnic między tekstami
def show_diff(text1, text2):
    import difflib
    d = difflib.Differ()
    diff = list(d.compare(text1.splitlines(), text2.splitlines()))
    return "\n".join(diff)

if __name__ == "__main__":
    test_sentences_anonymization()

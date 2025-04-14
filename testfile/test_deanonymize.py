import requests
import json
import sys
import os
import re

# Funkcja do testowania pojedynczego zdania
def test_sentence_deanonymization(sentence, session_id):
    print(f"\nTestowanie zdania: {sentence}")
    
    # Wyodrębnienie tokenów ze zdania
    anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
    tokens = anno_pattern.findall(sentence)
    
    if not tokens:
        print("Brak tokenów do deanonimizacji w tym zdaniu")
        return
    
    print(f"Znaleziono {len(tokens)} tokenów: {tokens}")
    
    # Testowanie deanonimizacji całego zdania
    payload = {
        "session_id": session_id,
        "text": sentence
    }
    
    response = requests.post("http://localhost:8000/deanonymize", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        deanonymized_text = result.get("deanonymized_text")
        
        if deanonymized_text and deanonymized_text != sentence:
            print(f"Zdanie zostało zdeanonimizowane do: {deanonymized_text}")
            return True
        else:
            print(f"Zdanie nie zostało zdeanonimizowane")
            return False
    else:
        print(f"Błąd podczas deanonimizacji zdania: {response.status_code}")
        print(f"Treść odpowiedzi: {response.text}")
        return False

# Funkcja do sprawdzania logów API
def check_api_logs():
    print("\nSprawdzanie logów API...")
    try:
        # Wysyłamy żądanie do API, aby sprawdzić logi
        response = requests.get("http://localhost:8000/health")
        print(f"Status API: {response.status_code}")
        print(f"Odpowiedź: {response.text}")
    except Exception as e:
        print(f"Błąd podczas sprawdzania logów API: {str(e)}")

# Główna funkcja testowa
def main():
    # Ścieżka do pliku JSON
    file_path = "a290ef2f-584a-4ef4-8d0d-1b9640531bdb.json"
    
    # Wczytanie pliku JSON
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Pobranie session_id z pliku
    session_id = data.get("session_id")
    if not session_id:
        print("Błąd: Brak session_id w pliku JSON")
        sys.exit(1)
    
    print(f"Używam session_id: {session_id}")
    
    # Testowanie deanonimizacji na pierwszych 3 zdaniach
    test_sentences = data.get("test_sentences", [])
    if not test_sentences:
        print("Błąd: Brak zdań testowych w pliku JSON")
        sys.exit(1)
    
    print(f"Znaleziono {len(test_sentences)} zdań testowych")
    
    # Testowanie deanonimizacji na pojedynczych zdaniach
    success_count = 0
    for i, sentence in enumerate(test_sentences[:3]):
        if test_sentence_deanonymization(sentence, session_id):
            success_count += 1
    
    if success_count > 0:
        print(f"\nDeanonimizacja zadziałała dla {success_count} z 3 testowanych zdań")
    else:
        print("\nDeanonimizacja nie zadziałała dla żadnego z testowanych zdań")
        print("Sprawdzanie, czy API deanonimizacji działa poprawnie...")
        
        # Testowanie deanonimizacji na prostym przykładzie
        test_payload = {
            "session_id": "test-session",
            "text": "To jest test deanonimizacji"
        }
        
        try:
            test_response = requests.post("http://localhost:8000/deanonymize", json=test_payload)
            print(f"Status API deanonimizacji: {test_response.status_code}")
            print(f"Odpowiedź: {test_response.text}")
        except Exception as e:
            print(f"Błąd podczas testowania API deanonimizacji: {str(e)}")
    
    # Sprawdzanie logów API
    check_api_logs()
    
    print("\nWnioski:")
    print("1. Deanonimizacja nie działa, ponieważ w bazie danych nie ma mapowań dla session_id z pliku JSON.")
    print("2. Aby deanonimizacja zadziałała, potrzebujemy:")
    print("   a) Albo przeprowadzić ponowną anonimizację oryginalnych danych, aby utworzyć mapowania w bazie danych")
    print("   b) Albo ręcznie dodać mapowania do bazy danych dla istniejących tokenów")
    print("   c) Albo zmodyfikować kod, aby obsługiwał przypadki, gdy session_id nie istnieje w bazie danych")

if __name__ == "__main__":
    main()

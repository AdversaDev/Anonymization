import requests
import json
import os
import sys
import time

def test_anonymization_and_deanonymization():
    """
    Przeprowadza pełny test procesu anonimizacji i deanonimizacji:
    1. Wysyła plik tekstowy do anonimizacji
    2. Otrzymuje zanonimizowany plik z tokenami anno_XXXXXXXX i session_id
    3. Wysyła zanonimizowany plik do deanonimizacji z tym samym session_id
    4. Sprawdza, czy tokeny zostały zdeanonimizowane
    """
    # Ścieżka do pliku tekstowego
    file_path = "test_anonymize.txt"
    
    # Sprawdzenie, czy plik istnieje
    if not os.path.exists(file_path):
        print(f"Błąd: Plik {file_path} nie istnieje")
        return
    
    # Krok 1: Anonimizacja pliku
    print("Krok 1: Wysyłanie pliku do anonimizacji...")
    
    # Przygotowanie pliku do wysłania
    files = {'file': (file_path, open(file_path, 'rb'), 'text/plain')}
    
    # Wysłanie żądania do API
    response = requests.post("http://localhost:8000/upload-anonymize", files=files)
    
    # Sprawdzenie odpowiedzi
    if response.status_code != 200:
        print(f"Błąd podczas anonimizacji: Kod odpowiedzi {response.status_code}")
        print(f"Treść odpowiedzi: {response.text}")
        return
    
    # Zapisanie zanonimizowanego pliku
    anonymized_file = "anonymized_test.txt"
    with open(anonymized_file, 'wb') as f:
        f.write(response.content)
    
    print(f"Anonimizacja zakończona sukcesem! Zapisano plik: {anonymized_file}")
    
    # Wczytanie zanonimizowanego pliku
    with open(anonymized_file, 'r', encoding='utf-8') as f:
        anonymized_text = f.read()
    
    # Wyodrębnienie session_id z pierwszej linii pliku
    session_id = None
    lines = anonymized_text.splitlines()
    if lines and lines[0].startswith("SessionID:"):
        session_id = lines[0].split("SessionID:")[1].strip()
        print(f"Wykryto session_id: {session_id}")
    else:
        print("Błąd: Nie można znaleźć session_id w zanonimizowanym pliku")
        return
    
    # Krok 2: Deanonimizacja pliku
    print("\nKrok 2: Wysyłanie pliku do deanonimizacji...")
    
    # Czekamy chwilę, aby upewnić się, że mapowania zostały zapisane w bazie danych
    print("Czekanie 2 sekundy, aby upewnić się, że mapowania zostały zapisane w bazie danych...")
    time.sleep(2)
    
    # Przygotowanie pliku do wysłania
    files = {'file': (anonymized_file, open(anonymized_file, 'rb'), 'text/plain')}
    
    # Przygotowanie formularza z session_id
    data = {'session_id': session_id}
    
    # Wysłanie żądania do API
    response = requests.post("http://localhost:8000/upload-deanonymize", files=files, data=data)
    
    # Sprawdzenie odpowiedzi
    if response.status_code != 200:
        print(f"Błąd podczas deanonimizacji: Kod odpowiedzi {response.status_code}")
        print(f"Treść odpowiedzi: {response.text}")
        return
    
    # Zapisanie zdeanonimizowanego pliku
    deanonymized_file = "deanonymized_test.txt"
    with open(deanonymized_file, 'wb') as f:
        f.write(response.content)
    
    print(f"Deanonimizacja zakończona sukcesem! Zapisano plik: {deanonymized_file}")
    
    # Wczytanie zdeanonimizowanego pliku
    with open(deanonymized_file, 'r', encoding='utf-8') as f:
        deanonymized_text = f.read()
    
    # Krok 3: Porównanie oryginalnego, zanonimizowanego i zdeanonimizowanego tekstu
    print("\nKrok 3: Porównanie tekstów...")
    
    # Wczytanie oryginalnego pliku
    with open(file_path, 'r', encoding='utf-8') as f:
        original_text = f.read()
    
    # Sprawdzenie, czy w zanonimizowanym tekście są tokeny anno_XXXXXXXX
    import re
    anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
    anno_tokens_in_anonymized = anno_pattern.findall(anonymized_text)
    
    # Sprawdzenie, czy w zdeanonimizowanym tekście są tokeny anno_XXXXXXXX
    anno_tokens_in_deanonymized = anno_pattern.findall(deanonymized_text)
    
    print(f"Liczba tokenów w zanonimizowanym tekście: {len(anno_tokens_in_anonymized)}")
    print(f"Liczba tokenów w zdeanonimizowanym tekście: {len(anno_tokens_in_deanonymized)}")
    
    if len(anno_tokens_in_deanonymized) < len(anno_tokens_in_anonymized):
        print("Sukces! Niektóre tokeny zostały zdeanonimizowane.")
        
        # Wyświetlenie fragmentów tekstu
        print("\nFragment oryginalnego tekstu:")
        print(original_text[:200] + "..." if len(original_text) > 200 else original_text)
        
        print("\nFragment zanonimizowanego tekstu:")
        print(anonymized_text[:200] + "..." if len(anonymized_text) > 200 else anonymized_text)
        
        print("\nFragment zdeanonimizowanego tekstu:")
        print(deanonymized_text[:200] + "..." if len(deanonymized_text) > 200 else deanonymized_text)
    else:
        print("Błąd: Tokeny nie zostały zdeanonimizowane.")
        
        # Sprawdzenie, czy zdeanonimizowany tekst jest identyczny z zanonimizowanym
        if anonymized_text == deanonymized_text:
            print("Zdeanonimizowany tekst jest identyczny z zanonimizowanym.")
        else:
            print("Zdeanonimizowany tekst różni się od zanonimizowanego, ale tokeny nie zostały zastąpione.")

if __name__ == "__main__":
    test_anonymization_and_deanonymization()

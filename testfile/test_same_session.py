import requests
import uuid
import re
import json
import sys

def test_anonymization_deanonymization_with_same_session():
    """
    Test anonimizacji i deanonimizacji z tym samym session_id.
    1. Generuje session_id
    2. Anonimizuje tekst z tym session_id
    3. Deanonimizuje zanonimizowany tekst z tym samym session_id
    4. Sprawdza, czy zdeanonimizowany tekst jest identyczny z oryginalnym
    """
    # Generujemy unikalny session_id
    session_id = str(uuid.uuid4())
    print(f"Używam session_id: {session_id}")
    
    # Przykładowy tekst do anonimizacji
    original_text = "Guten Morgen, mein Name ist Jan Kowalski. Ich arbeite als Arzt in der St.-Anna-Klinik in Hamburg."
    print(f"Oryginalny tekst: {original_text}")
    
    # Krok 1: Anonimizacja tekstu z podanym session_id
    print("Krok 1: Wysyłanie tekstu do anonimizacji...")
    response = requests.post(
        "http://localhost:8001/anonymize",
        json={"text": original_text, "session_id": session_id}
    )
    
    if response.status_code != 200:
        print(f"Błąd podczas anonimizacji: {response.status_code}, {response.text}")
        return
    
    result = response.json()
    anonymized_text = result.get("anonymized_text")
    
    if not anonymized_text:
        print("Błąd: Brak zanonimizowanego tekstu w odpowiedzi")
        return
    
    print(f"Zanonimizowany tekst: {anonymized_text}")
    
    # Wyodrębniamy tokeny z zanonimizowanego tekstu
    anno_pattern = re.compile(r'anno_[a-f0-9]{8}')
    anno_tokens = anno_pattern.findall(anonymized_text)
    unique_tokens = sorted(set(anno_tokens))
    
    print(f"Znaleziono {len(unique_tokens)} unikalnych tokenów: {', '.join(unique_tokens)}")
    
    # Krok 2: Deanonimizacja tekstu z tym samym session_id
    print("\nKrok 2: Wysyłanie tekstu do deanonimizacji...")
    response = requests.post(
        "http://localhost:8001/deanonymize",
        json={"text": anonymized_text, "session_id": session_id}
    )
    
    if response.status_code != 200:
        print(f"Błąd podczas deanonimizacji: {response.status_code}, {response.text}")
        return
    
    result = response.json()
    deanonymized_text = result.get("deanonymized_text")
    
    if not deanonymized_text:
        print("Błąd: Brak zdeanonimizowanego tekstu w odpowiedzi")
        return
    
    print(f"Zdeanonimizowany tekst: {deanonymized_text}")
    
    # Krok 3: Sprawdzenie, czy deanonimizacja była udana
    if deanonymized_text == original_text:
        print("\nTest zakończony sukcesem! Zdeanonimizowany tekst jest identyczny z oryginalnym.")
    else:
        print("\nTest zakończony niepowodzeniem. Zdeanonimizowany tekst różni się od oryginalnego.")
        print("Różnice:")
        import difflib
        d = difflib.Differ()
        diff = list(d.compare(original_text.splitlines(), deanonymized_text.splitlines()))
        print("\n".join(diff))
    
    # Zapisujemy wyniki do pliku
    results = {
        "session_id": session_id,
        "original_text": original_text,
        "anonymized_text": anonymized_text,
        "deanonymized_text": deanonymized_text,
        "tokens": unique_tokens,
        "success": deanonymized_text == original_text
    }
    
    with open("test_same_session_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nWyniki testu zapisane do pliku test_same_session_results.json")

if __name__ == "__main__":
    test_anonymization_deanonymization_with_same_session()

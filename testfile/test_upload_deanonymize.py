import requests
import json
import os
import sys

def test_upload_deanonymize():
    """
    Test funkcji upload_deanonymize, która teraz używa tego samego mechanizmu co w Postmanie.
    """
    # Ścieżka do pliku JSON
    file_path = "a290ef2f-584a-4ef4-8d0d-1b9640531bdb.json"
    
    # Sprawdzenie, czy plik istnieje
    if not os.path.exists(file_path):
        print(f"Błąd: Plik {file_path} nie istnieje")
        return
    
    # Wczytanie pliku JSON
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Pobranie session_id z pliku
    session_id = data.get("session_id")
    if not session_id:
        print("Błąd: Brak session_id w pliku JSON")
        return
    
    print(f"Używam session_id: {session_id}")
    
    # Przygotowanie pliku do wysłania
    files = {'file': (file_path, open(file_path, 'rb'), 'application/json')}
    
    # Przygotowanie formularza z session_id
    data = {'session_id': session_id}
    
    # Wysłanie żądania do API
    print("Wysyłanie pliku do deanonimizacji...")
    response = requests.post("http://localhost:8000/upload-deanonymize", files=files, data=data)
    
    # Sprawdzenie odpowiedzi
    if response.status_code == 200:
        print("Deanonimizacja zakończona sukcesem!")
        
        # Zapisanie zdeanonimizowanego pliku
        output_file = f"test_deanonymized_{session_id}.json"
        with open(output_file, 'wb') as f:
            f.write(response.content)
        
        print(f"Zapisano zdeanonimizowany plik: {output_file}")
        
        # Wczytanie zdeanonimizowanego pliku JSON
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                deanonymized_data = json.load(f)
            
            # Wyświetlenie pierwszych kilku zdań przed i po deanonimizacji
            print("\nPorównanie pierwszych 3 zdań przed i po deanonimizacji:")
            for i in range(min(3, len(data.get("test_sentences", [])))):
                original = data["test_sentences"][i]
                deanonymized = deanonymized_data["test_sentences"][i] if "test_sentences" in deanonymized_data else "Brak zdań w zdeanonimizowanym pliku"
                print(f"\nZdanie {i+1}:")
                print(f"Oryginalne: {original}")
                print(f"Zdeanonimizowane: {deanonymized}")
                
                # Sprawdzenie, czy zdanie zostało zdeanonimizowane
                if original == deanonymized:
                    print("Status: Nie zdeanonimizowano")
                else:
                    print("Status: Zdeanonimizowano")
        except Exception as e:
            print(f"Błąd podczas analizy zdeanonimizowanego pliku: {str(e)}")
    else:
        print(f"Błąd: Kod odpowiedzi {response.status_code}")
        print(f"Treść odpowiedzi: {response.text}")

if __name__ == "__main__":
    test_upload_deanonymize()

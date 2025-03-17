import sys
import os

# Ustawienie ścieżki do katalogu nadrzędnego (aby Python widział `app`)
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from anonymizer import anonymize_text  # Importuj bez `app.`

# Przykładowy tekst do testowania
text = "Guten Tag, mein Name ist Tobias Müller und ich wohne in der Friedrichstraße 123, 10117 Berlin."

session_id = "test-session-123"

anonymized_text = anonymize_text(session_id, text)

print("\n🔍 Wynik anonimizacji:")
print(anonymized_text)

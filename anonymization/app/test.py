import requests
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://localhost:8001/anonymize"

# 🔹 Funkcja do normalizacji tekstu (usuwa spacje, poprawia interpunkcję)
def normalize_text(text):
    text = text.strip()  
    text = re.sub(r"\s+", " ", text)  
    text = text.replace(" ,", ",").replace(" .", ".")  
    return text

# ✅ ŁATWE PRZYPADKI (poprawne niemieckie formaty)
EASY_TESTS = [
    {
        "text": "Mein Name ist Anna Schmidt und ich wohne in der Hauptstraße 5, 10115 Berlin.",
        "expected": "Mein Name ist <PERSON> und ich wohne in der Hauptstraße 5, <ZIP_CODE> <LOCATION>."
    },
    {
        "text": "Meine E-Mail ist anna.schmidt@gmail.com.",
        "expected": "Meine E-Mail ist <EMAIL_ADDRESS>."
    },
    {
        "text": "Meine Telefonnummer ist +49 176 6543210.",
        "expected": "Meine Telefonnummer ist <PHONE_NUMBER>."
    },
    {
        "text": "Mein IBAN ist DE44500105175407324931.",
        "expected": "Mein IBAN ist <IBAN_CODE>."
    },
    {
        "text": "Meine Kreditkartennummer lautet 4111-1111-1111-1111.",
        "expected": "Meine Kreditkartennummer lautet <CREDIT_CARD>."
    },
    {
        "text": "Meine Steuernummer ist 22/815/08151.",
        "expected": "Meine Steuernummer ist <TAX_ID>."
    },
    {
        "text": "Ich wurde am 03. Dezember 1990 geboren.",
        "expected": "Ich wurde am <DATE> geboren."
    },
    {
        "text": "Mein Code pocztowy to 80331 München.",
        "expected": "Mein Code pocztowy to <ZIP_CODE> <LOCATION>."
    }
]

# ❌ TRUDNE PRZYPADKI (możliwe błędy w anonimizacji)
HARD_TESTS = [
    {
        "text": "Mein Name ist Max Mustermann und ich wohne in 60594 Frankfurt am Main.",
        "expected": "Mein Name ist <PERSON> und ich wohne in <ZIP_CODE> <LOCATION>.",
        "possible_issues": "Czy ZIP_CODE działa dla Frankfurt am Main?"
    },
    {
        "text": "Meine Steuernummer lautet 302/815/08157.",
        "expected": "Meine Steuernummer lautet <TAX_ID>.",
        "possible_issues": "Czy Steuernummer z innym formatem jest wykrywana?"
    },
    {
        "text": "Meine Kreditkartennummer ist 6011-1234-5678-9012.",
        "expected": "Meine Kreditkartennummer ist <CREDIT_CARD>.",
        "possible_issues": "Czy Diners Club (6011) jest poprawnie wykrywany?"
    },
    {
        "text": "Ich wurde am 01-05-1987 geboren.",
        "expected": "Ich wurde am <DATE> geboren.",
        "possible_issues": "Czy format `dd-mm-yyyy` jest poprawnie wykrywany?"
    },
    {
        "text": "Meine Adresse ist Brückenstraße 7, 01067 Dresden.",
        "expected": "Meine Adresse ist <LOCATION>, <ZIP_CODE> <LOCATION>.",
        "possible_issues": "Czy ZIP_CODE i LOCATION są wykrywane jednocześnie?"
    },
    {
        "text": "Mein IBAN ist DE89370400440532013000.",
        "expected": "Mein IBAN ist <IBAN_CODE>.",
        "possible_issues": "Czy wszystkie niemieckie IBAN są poprawnie wykrywane?"
    }
]

def run_tests(test_cases, category):
    print(f"\n🔹 Testowanie: {category}")
    for test in test_cases:
        response = requests.post(API_URL, json={"text": test["text"]})
        result = normalize_text(response.json()["anonymized_text"])
        expected = normalize_text(test["expected"])

        if result == expected:
            print(f"✅ PASSED: {test['text']}")
        else:
            print(f"❌ FAILED: {test['text']}")
            print(f"   🔹 Expected: {expected}")
            print(f"   🔸 Got: {result}")

run_tests(EASY_TESTS, "ŁATWE PRZYPADKI")
run_tests(HARD_TESTS, "TRUDNE PRZYPADKI")

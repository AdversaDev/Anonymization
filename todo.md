# Lista zadań do wykonania w systemie anonimizacji

## Priorytetowe zadania

### 1. Ulepszenie wykrywania i łączenia adresów
- [ ] Zaimplementować bardziej efektywny algorytm łączenia elementów adresów (ulica, kod pocztowy, miasto) w jeden token
- [ ] Dodać post-processing wykrytych encji, który będzie łączył blisko położone elementy adresów
- [ ] Rozszerzyć wzorce adresów o więcej formatów niemieckich adresów
- [ ] Uwzględnić różne przyimki i konteksty występowania adresów (nach, in, bei, etc.)

### 2. Optymalizacja wykrywania dat
- [ ] Poprawić wykrywanie dat w formatach bez kropki po dniu (np. "15 Januar 1910")
- [ ] Dodać obsługę dat ze skróconymi nazwami miesięcy (Jan, Feb, etc.)
- [ ] Uwzględnić daty z apostrofem dla lat (np. '23 zamiast 2023)

### 3. Ulepszenie wykrywania tablic rejestracyjnych
- [ ] Dopracować wzorce dla niemieckich tablic rejestracyjnych (M AB 123, B C 1, etc.)
- [ ] Uwzględnić różne formaty i warianty tablic rejestracyjnych

### 4. Rozszerzenie obsługi imion
- [ ] Poprawić wykrywanie imion zaczynających się na E i kończących na a/e (Eva, Emma, Elena, etc.)
- [ ] Rozszerzyć słownik imion o więcej przykładów
- [ ] Uwzględnić kontekst występowania imion (np. po tytułach naukowych)

## Zadania techniczne

### 1. Refaktoryzacja kodu
- [ ] Wydzielić logikę wykrywania adresów do osobnego modułu
- [ ] Poprawić strukturę kodu dla lepszej czytelności i utrzymania
- [ ] Dodać więcej komentarzy i dokumentacji

### 2. Testy i walidacja
- [ ] Rozszerzyć zestaw testów o więcej przypadków brzegowych
- [ ] Dodać testy jednostkowe dla poszczególnych komponentów
- [ ] Zaimplementować automatyczne testy regresji

### 3. Optymalizacja wydajności
- [ ] Zoptymalizować algorytmy wykrywania encji dla lepszej wydajności
- [ ] Zmniejszyć liczbę fałszywych trafień
- [ ] Poprawić obsługę nakładających się encji

## Zadania długoterminowe

### 1. Rozszerzenie funkcjonalności
- [ ] Dodać obsługę więcej typów danych osobowych
- [ ] Zaimplementować wykrywanie i anonimizację numerów paszportów
- [ ] Dodać obsługę więcej formatów adresów e-mail i stron internetowych

### 2. Integracja z innymi systemami
- [ ] Przygotować API do integracji z innymi systemami
- [ ] Dodać możliwość eksportu i importu danych

### 3. Dokumentacja i wsparcie
- [ ] Przygotować szczegółową dokumentację użytkownika
- [ ] Stworzyć przykłady użycia dla różnych scenariuszy

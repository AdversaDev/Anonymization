#!/usr/bin/env python
"""
Skrypt testowy do sprawdzenia działania mechanizmu czyszczenia sesji.
"""

import os
import sys
import datetime
import psycopg2
import uuid
import argparse

# Dodanie ścieżki do katalogu nadrzędnego, aby umożliwić import modułów
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Bezpośredni import funkcji z pliku cleanup_sessions.py
sys.path.append('/app')

# Definicja funkcji get_db_connection
def get_db_connection():
    """Ustanawia połączenie z bazą danych."""
    try:
        DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://anon_user:securepassword@db:5432/anon_db")
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Błąd podczas łączenia z bazą danych: {e}")
        sys.exit(1)

# Definicja funkcji cleanup_old_sessions
def cleanup_old_sessions(days=7, dry_run=False):
    """Usuwa sesje starsze niż określona liczba dni."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Najpierw sprawdzamy, czy tabela anonymization ma kolumnę created_at
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'anonymization' AND column_name = 'created_at'
        """)
        
        has_created_at = cursor.fetchone() is not None
        
        if not has_created_at:
            print("Tabela anonymization nie ma kolumny created_at. Dodawanie kolumny...")
            
            if not dry_run:
                # Dodajemy kolumnę created_at, jeśli nie istnieje
                cursor.execute("""
                    ALTER TABLE anonymization 
                    ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                """)
                conn.commit()
                print("Dodano kolumnę created_at do tabeli anonymization.")
            else:
                print("[DRY RUN] Dodano by kolumnę created_at do tabeli anonymization.")
            
            # Ponieważ właśnie dodaliśmy kolumnę created_at, nie ma starych sesji do usunięcia
            print("Brak starych sesji do usunięcia, ponieważ właśnie dodano kolumnę created_at.")
            return 0
        
        # Obliczamy datę graniczną (z uwzględnieniem strefy czasowej)
        cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        
        # Najpierw identyfikujemy sesje do usunięcia
        cursor.execute("""
            SELECT DISTINCT session_id, MIN(created_at) as oldest_entry
            FROM anonymization
            GROUP BY session_id
            HAVING MIN(created_at) < %s
        """, (cutoff_date,))
        
        old_sessions = cursor.fetchall()
        session_count = len(old_sessions)
        
        if session_count == 0:
            print(f"Nie znaleziono sesji starszych niż {days} dni.")
            return 0
        
        print(f"Znaleziono {session_count} sesji starszych niż {days} dni.")
        
        # Wyświetlamy szczegóły sesji do usunięcia
        for session_id, oldest_entry in old_sessions:
            days_old = (datetime.datetime.now(datetime.timezone.utc) - oldest_entry).days
            print(f"Sesja {session_id} - najstarszy wpis: {oldest_entry} ({days_old} dni temu)")
        
        if dry_run:
            print(f"[DRY RUN] Znaleziono {session_count} sesji do usunięcia.")
            return session_count
        
        # Usuwamy stare sesje
        for session_id, _ in old_sessions:
            cursor.execute("""
                DELETE FROM anonymization
                WHERE session_id = %s
            """, (session_id,))
            print(f"Usunięto sesję {session_id}")
        
        conn.commit()
        print(f"Pomyślnie usunięto {session_count} starych sesji.")
        
        return session_count
    
    except Exception as e:
        conn.rollback()
        print(f"Błąd podczas czyszczenia starych sesji: {e}")
        return 0
    
    finally:
        cursor.close()
        conn.close()

def create_test_sessions(num_sessions=5, days_old=10):
    """
    Tworzy testowe sesje w bazie danych, które są starsze o określoną liczbę dni.
    
    Args:
        num_sessions (int): Liczba sesji do utworzenia
        days_old (int): Liczba dni, o które sesje mają być starsze
    
    Returns:
        list: Lista utworzonych identyfikatorów sesji
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Sprawdzamy, czy tabela anonymization ma kolumnę created_at
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'anonymization' AND column_name = 'created_at'
    """)
    
    has_created_at = cursor.fetchone() is not None
    
    if not has_created_at:
        # Dodajemy kolumnę created_at, jeśli nie istnieje
        cursor.execute("""
            ALTER TABLE anonymization 
            ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        """)
        conn.commit()
        print("Dodano kolumnę created_at do tabeli anonymization.")
    
    # Obliczamy datę dla starych sesji (z uwzględnieniem strefy czasowej)
    old_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_old)
    
    # Tworzymy testowe sesje
    session_ids = []
    for i in range(num_sessions):
        session_id = str(uuid.uuid4())
        session_ids.append(session_id)
        
        # Dodajemy testowe mapowania dla sesji
        cursor.execute("""
            INSERT INTO anonymization (session_id, anon_id, original_value, entity_type, created_at) 
            VALUES (%s, %s, %s, %s, %s)
        """, (session_id, f"anno_test_{i}", f"Test Value {i}", "PERSON", old_date))
        
        print(f"Utworzono testową sesję {session_id} (stara o {days_old} dni)")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return session_ids

def create_recent_session():
    """
    Tworzy testową sesję, która jest aktualna (nie powinna być usunięta).
    
    Returns:
        str: Identyfikator utworzonej sesji
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    session_id = str(uuid.uuid4())
    
    # Dodajemy testowe mapowania dla sesji
    cursor.execute("""
        INSERT INTO anonymization (session_id, anon_id, original_value, entity_type) 
        VALUES (%s, %s, %s, %s)
    """, (session_id, "anno_recent", "Recent Test Value", "PERSON"))
    
    print(f"Utworzono testową sesję {session_id} (aktualna)")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return session_id

def check_session_exists(session_id):
    """
    Sprawdza, czy sesja istnieje w bazie danych.
    
    Args:
        session_id (str): Identyfikator sesji do sprawdzenia
    
    Returns:
        bool: True, jeśli sesja istnieje, False w przeciwnym razie
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) FROM anonymization WHERE session_id = %s
    """, (session_id,))
    
    count = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    return count > 0

def main():
    """Główna funkcja skryptu testowego."""
    parser = argparse.ArgumentParser(description="Testuje mechanizm czyszczenia sesji.")
    parser.add_argument("--create-only", action="store_true", help="Tylko utwórz testowe sesje, bez testowania czyszczenia")
    parser.add_argument("--num-sessions", type=int, default=5, help="Liczba testowych sesji do utworzenia (domyślnie: 5)")
    parser.add_argument("--days-old", type=int, default=10, help="Liczba dni, o które testowe sesje mają być starsze (domyślnie: 10)")
    parser.add_argument("--cleanup-days", type=int, default=7, help="Liczba dni dla mechanizmu czyszczenia (domyślnie: 7)")
    
    args = parser.parse_args()
    
    print("=== Test mechanizmu czyszczenia sesji ===")
    
    # Tworzenie testowych starych sesji
    print(f"\nTworzenie {args.num_sessions} testowych sesji starszych o {args.days_old} dni...")
    old_session_ids = create_test_sessions(num_sessions=args.num_sessions, days_old=args.days_old)
    
    # Tworzenie testowej aktualnej sesji
    print("\nTworzenie testowej aktualnej sesji...")
    recent_session_id = create_recent_session()
    
    if args.create_only:
        print("\nUtworzone testowe sesje:")
        print(f"Stare sesje (powinny być usunięte): {', '.join(old_session_ids)}")
        print(f"Aktualna sesja (nie powinna być usunięta): {recent_session_id}")
        print("\nTest zakończony. Uruchom skrypt czyszczenia sesji, aby przetestować usuwanie.")
        return
    
    # Uruchomienie mechanizmu czyszczenia sesji
    print(f"\nUruchamianie mechanizmu czyszczenia sesji (usuwanie sesji starszych niż {args.cleanup_days} dni)...")
    deleted_count = cleanup_old_sessions(days=args.cleanup_days)
    
    print(f"\nMechanizm czyszczenia usunął {deleted_count} sesji.")
    
    # Sprawdzenie, czy stare sesje zostały usunięte
    print("\nSprawdzanie, czy stare sesje zostały usunięte...")
    old_sessions_remaining = 0
    for session_id in old_session_ids:
        exists = check_session_exists(session_id)
        status = "ISTNIEJE (BŁĄD)" if exists else "USUNIĘTA (OK)"
        print(f"Sesja {session_id}: {status}")
        if exists:
            old_sessions_remaining += 1
    
    # Sprawdzenie, czy aktualna sesja nie została usunięta
    print("\nSprawdzanie, czy aktualna sesja nie została usunięta...")
    recent_exists = check_session_exists(recent_session_id)
    recent_status = "ISTNIEJE (OK)" if recent_exists else "USUNIĘTA (BŁĄD)"
    print(f"Sesja {recent_session_id}: {recent_status}")
    
    # Podsumowanie testu
    print("\n=== Podsumowanie testu ===")
    if old_sessions_remaining == 0 and recent_exists:
        print("TEST ZAKOŃCZONY SUKCESEM: Wszystkie stare sesje zostały usunięte, a aktualna sesja pozostała.")
    else:
        print(f"TEST ZAKOŃCZONY NIEPOWODZENIEM: {old_sessions_remaining} starych sesji pozostało, aktualna sesja {'istnieje' if recent_exists else 'została usunięta'}.")

if __name__ == "__main__":
    main()

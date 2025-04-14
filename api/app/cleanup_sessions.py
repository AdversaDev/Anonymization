#!/usr/bin/env python
"""
Skrypt do czyszczenia starych sesji anonimizacji.
Usuwa sesje starsze niż określona liczba dni.
"""

import os
import sys
import logging
import datetime
import psycopg2
from psycopg2 import sql
import argparse

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("cleanup_sessions")

# Pobieranie parametrów połączenia z bazy danych z zmiennych środowiskowych
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://anon_user:securepassword@db:5432/anon_db")

def get_db_connection():
    """Ustanawia połączenie z bazą danych."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Błąd podczas łączenia z bazą danych: {e}")
        sys.exit(1)

def cleanup_old_sessions(days=7, dry_run=False):
    """
    Usuwa sesje starsze niż określona liczba dni.
    
    Args:
        days (int): Liczba dni, po których sesje są uznawane za stare
        dry_run (bool): Jeśli True, tylko wyświetla sesje do usunięcia, bez faktycznego usuwania
    
    Returns:
        int: Liczba usuniętych sesji
    """
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
            logger.info("Tabela anonymization nie ma kolumny created_at. Dodawanie kolumny...")
            
            if not dry_run:
                # Dodajemy kolumnę created_at, jeśli nie istnieje
                cursor.execute("""
                    ALTER TABLE anonymization 
                    ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                """)
                conn.commit()
                logger.info("Dodano kolumnę created_at do tabeli anonymization.")
            else:
                logger.info("[DRY RUN] Dodano by kolumnę created_at do tabeli anonymization.")
            
            # Ponieważ właśnie dodaliśmy kolumnę created_at, nie ma starych sesji do usunięcia
            logger.info("Brak starych sesji do usunięcia, ponieważ właśnie dodano kolumnę created_at.")
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
            logger.info(f"Nie znaleziono sesji starszych niż {days} dni.")
            return 0
        
        logger.info(f"Znaleziono {session_count} sesji starszych niż {days} dni.")
        
        # Wyświetlamy szczegóły sesji do usunięcia
        for session_id, oldest_entry in old_sessions:
            days_old = (datetime.datetime.now(datetime.timezone.utc) - oldest_entry).days
            logger.info(f"Sesja {session_id} - najstarszy wpis: {oldest_entry} ({days_old} dni temu)")
        
        if dry_run:
            logger.info(f"[DRY RUN] Znaleziono {session_count} sesji do usunięcia.")
            return session_count
        
        # Usuwamy stare sesje
        for session_id, _ in old_sessions:
            cursor.execute("""
                DELETE FROM anonymization
                WHERE session_id = %s
            """, (session_id,))
            logger.info(f"Usunięto sesję {session_id}")
        
        conn.commit()
        logger.info(f"Pomyślnie usunięto {session_count} starych sesji.")
        
        return session_count
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Błąd podczas czyszczenia starych sesji: {e}")
        return 0
    
    finally:
        cursor.close()
        conn.close()

def main():
    """Główna funkcja skryptu."""
    parser = argparse.ArgumentParser(description="Czyści stare sesje anonimizacji z bazy danych.")
    parser.add_argument("--days", type=int, default=7, help="Usuń sesje starsze niż określona liczba dni (domyślnie: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Tylko wyświetl sesje do usunięcia, bez faktycznego usuwania")
    
    args = parser.parse_args()
    
    logger.info(f"Rozpoczynanie czyszczenia sesji starszych niż {args.days} dni...")
    
    if args.dry_run:
        logger.info("Tryb DRY RUN - żadne dane nie zostaną usunięte.")
    
    deleted_count = cleanup_old_sessions(days=args.days, dry_run=args.dry_run)
    
    if args.dry_run:
        logger.info(f"[DRY RUN] Znaleziono {deleted_count} sesji do usunięcia.")
    else:
        logger.info(f"Czyszczenie zakończone. Usunięto {deleted_count} sesji.")

if __name__ == "__main__":
    main()

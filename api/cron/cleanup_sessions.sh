#!/bin/bash
# Skrypt do uruchamiania czyszczenia sesji przez cron

# Ustawienie ścieżki do Pythona
PYTHON_PATH=$(which python)

# Ścieżka do skryptu czyszczenia sesji
CLEANUP_SCRIPT="/app/app/cleanup_sessions.py"

# Ustawienie zmiennych środowiskowych
export DATABASE_URL="postgresql://anon_user:securepassword@db:5432/anon_db"

# Uruchomienie skryptu czyszczenia z logowaniem
echo "$(date) - Rozpoczęcie czyszczenia starych sesji" >> /var/log/cleanup_sessions.log
$PYTHON_PATH $CLEANUP_SCRIPT --days 7 >> /var/log/cleanup_sessions.log 2>&1
echo "$(date) - Zakończenie czyszczenia starych sesji" >> /var/log/cleanup_sessions.log

#!/bin/bash
# Skrypt startowy dla kontenera API

# Funkcja do czyszczenia sesji
cleanup_sessions() {
    echo "$(date) - Uruchamianie czyszczenia starych sesji..." >> /var/log/cleanup_sessions.log
    python /app/app/cleanup_sessions.py --days 7 >> /var/log/cleanup_sessions.log 2>&1
    echo "$(date) - Zakończenie czyszczenia starych sesji" >> /var/log/cleanup_sessions.log
}

# Funkcja uruchamiająca czyszczenie sesji w tle
run_cleanup_in_background() {
    while true; do
        # Czyszczenie sesji o północy
        current_hour=$(date +%H)
        if [ "$current_hour" == "00" ]; then
            cleanup_sessions
        fi
        
        # Sprawdzanie co godzinę
        sleep 3600
    done
}

# Uruchomienie czyszczenia sesji w tle
run_cleanup_in_background &

# Uruchomienie aplikacji na pierwszym planie
echo "$(date) - Uruchamianie aplikacji API..." >> /var/log/api.log
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

FROM python:3.10

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Kopiowanie aplikacji
COPY ./app /app/app 

# Tworzenie katalogu na logi
RUN mkdir -p /var/log

# Tworzenie skryptu startowego
COPY ./start.sh /app/start.sh
RUN chmod +x /app/start.sh

WORKDIR /app

# Poprawne ustawienie PYTHONPATH, aby importy działały
ENV PYTHONPATH="/app"

# Uruchomienie skryptu startowego
CMD ["/app/start.sh"]

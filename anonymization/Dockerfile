FROM python:3.10

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Pobranie modelu językowego do Presidio
RUN python -m spacy download de_core_news_lg

COPY ./app /app/app

WORKDIR /app

# Poprawne ustawienie PYTHONPATH, aby importy działały
ENV PYTHONPATH="/app"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

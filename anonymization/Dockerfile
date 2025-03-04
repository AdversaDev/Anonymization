FROM python:3.10

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# Pobranie i instalacja wymaganych modeli językowych
RUN python -m spacy download en_core_web_lg
RUN python -m spacy download pl_core_news_lg
RUN python -m spacy download de_core_news_lg



COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

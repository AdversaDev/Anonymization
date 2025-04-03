FROM python:3.10

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./app /app/app 

WORKDIR /app

# Poprawne ustawienie PYTHONPATH, aby importy działały
ENV PYTHONPATH="/app"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

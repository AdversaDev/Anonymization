
🚀 Installation & Setup

👁 1. Clone the Repository

git clone https://github.com/AdversaDev/Anonymization.git
cd Anonymization

💧 2. Start with Docker

docker-compose up --build -d

This will start:

API at http://localhost:8000

Anonymization Service at http://localhost:8001

PostgreSQL Database

⚡ Using the API

🔹 Anonymization

curl -X POST "http://localhost:8000/anonymize" \
     -H "Content-Type: application/json" \
     -d '{"text": "John Doe, born on March 12, 1985, lives in New York."}'

Response:

{
  "session_id": "12345678-abcd-4321-efgh-56789ijklmn",
  "anonymized_text": "anno_1234, born on anno_5678, lives in anno_9012."
}

🔹 De-Anonymization

curl -X POST "http://localhost:8000/deanonymize" \
     -H "Content-Type: application/json" \
     -d '{"session_id": "12345678-abcd-4321-efgh-56789ijklmn", "text": "anno_1234 was born on anno_5678."}'

Response:

{
  "deanonymized_text": "John Doe was born on March 12, 1985."
}

🛠️ Configuration

docker-compose.yml – Defines the Docker services.

config.py – Contains API configuration parameters.

db/init.sql – Creates the PostgreSQL table for anonymization.

📚 License

This project is licensed under the MIT License.

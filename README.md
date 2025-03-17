# 🛡️ Anonymisierungssystem

> **Ein leistungsstarkes Tool zur Erkennung und Anonymisierung sensibler Daten**

## 🔍 Übersicht
Dieses Projekt bietet eine **Lösung zur Anonymisierung von Daten** mit **FastAPI** und **PostgreSQL**. Es nutzt **Presidio** zur Erkennung und Anonymisierung personenbezogener Informationen.

⚡ **Technologien:** FastAPI | PostgreSQL | Presidio | Docker

---

## 🚀 Installation & Einrichtung

### 📥 1. Repository klonen
```bash
git clone https://github.com/AdversaDev/Anonymization.git
cd Anonymization
```

### 🛠️ 2. Mit Docker starten
```bash
docker-compose up --build -d
```

🔹 **Dienste werden gestartet:**
- **API**: `http://localhost:8000`
- **Anonymisierungsdienst**: `http://localhost:8001`
- **PostgreSQL-Datenbank**

---

## ⚡ Nutzung der API

### 🔹 **Anonymisierung von Texten**
**Anfrage:**
```bash
curl -X POST "http://localhost:8000/anonymize" \
     -H "Content-Type: application/json" \
     -d '{"text": "Max Mustermann, geboren am 12. März 1985, lebt in Berlin."}'
```

**Antwort:**
```json
{
  "session_id": "12345678-abcd-4321-efgh-56789ijklmn",
  "anonymized_text": "anno_1234, geboren am anno_5678, lebt in anno_9012."
}
```

### 🔹 **De-Anonymisierung von Texten**
**Anfrage:**
```bash
curl -X POST "http://localhost:8000/deanonymize" \
     -H "Content-Type: application/json" \
     -d '{"session_id": "12345678-abcd-4321-efgh-56789ijklmn", "text": "anno_1234 wurde am anno_5678 geboren."}'
```

**Antwort:**
```json
{
  "deanonymized_text": "Max Mustermann wurde am 12. März 1985 geboren."
}
```

---

## 🔧 Konfiguration
| Datei                | Beschreibung |
|----------------------|--------------|
| `docker-compose.yml` | Definiert die Docker-Dienste |
| `config.py` | Enthält API-Konfigurationsparameter |
| `db/init.sql` | Erstellt die PostgreSQL-Tabelle zur Anonymisierung |

---

## 🎯 Funktionsweise
1. **Erkennung:** Identifikation von Namen, Telefonnummern, E-Mails, Adressen uvm.
2. **Anonymisierung:** Ersetzen von sensiblen Informationen durch eindeutige Tokens.
3. **De-Anonymisierung:** Wiederherstellung der ursprünglichen Daten basierend auf einer Sitzung.

---

## 📄 Lizenz
Dieses Projekt steht unter der **MIT-Lizenz**.

📌 **AdversaDev** – [GitHub](https://github.com/AdversaDev) 🚀


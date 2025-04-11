import http from 'k6/http';
import { check, sleep } from 'k6';

// Konfiguracja testu obciążeniowego
export const options = {
  // Opcja 1: Stała liczba użytkowników przez określony czas
  vus: 10,                // 50 jednoczesnych użytkowników
  duration: '2m',         // Test trwa 2 minuty
  
  // Opcja 2: Stopniowe zwiększanie obciążenia (odkomentuj, aby użyć)
  // stages: [
  //   { duration: '30s', target: 20 },  // Zwiększ do 20 użytkowników w ciągu 30 sekund
  //   { duration: '1m', target: 50 },   // Zwiększ do 50 użytkowników w ciągu 1 minuty
  //   { duration: '2m', target: 100 },  // Zwiększ do 100 użytkowników w ciągu 2 minut
  //   { duration: '1m', target: 0 },    // Stopniowo zmniejszaj do 0 użytkowników
  // ],
  
  // Progi wydajności
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% żądań powinno być poniżej 500ms
    http_req_failed: ['rate<0.01'],    // Mniej niż 1% żądań może się nie powieść
  },
};


// Dłuższe teksty symulujące dokumenty do anonimizacji
const longDocuments = [
  {
    session_id: "doc-session-1",
    text: `PATIENTENAKTE
Musterklinik Berlin - Ärztlicher Entlassungsbericht
Patientenname: Herr Dr. med. Johannes Meier
Geburtsdatum: 03.02.1956
Versichertennummer: TK-9876543210
Adresse: Lindenstraße 45, 10969 Berlin
Telefonnummer: +49 30 123456789
E-Mail: j.meier@beispiel.de
Aufnahmedatum: 05.03.2024
Entlassungsdatum: 14.03.2024
Behandelnder Arzt: Dr. med. Clara Hoffmann, Approbationsnummer: 55667788

Diagnosen:
Hauptdiagnose:

Akuter Myokardinfarkt (STEMI, Vorderwand)

Nebendiagnosen:

Arterielle Hypertonie

Hyperlipidämie

Nikotinabusus (seit 25 Jahren, 20 Zigaretten/Tag)

Zustand nach Appendektomie (1980)

Verlauf & Therapie:
Der Patient wurde am 05.03.2024 mit akutem Thoraxschmerz über die Notaufnahme eingewiesen. Im EKG zeigte sich ein ST-Strecken-Hebungsinfarkt der Vorderwand. Die sofortige Koronarangiographie (06.03.2024) ergab eine hochgradige Stenose des Ramus interventricularis anterior, welche mittels DES-Stent (Abbott Xience Sierra 3.0 x 18 mm) versorgt wurde. Die postinterventionelle Therapie umfasste ASS, Ticagrelor, Atorvastatin, Bisoprolol und Ramipril.

Während des stationären Aufenthalts wurde eine strukturierte kardiologische Frührehabilitation durchgeführt. Blutdruck und Lipidwerte konnten medikamentös stabilisiert werden. Eine Nikotinentwöhnung wurde empfohlen.

Laborwerte bei Entlassung (13.03.2024):
Troponin T: 0.02 ng/mL (↓)

LDL-Cholesterin: 92 mg/dL

HbA1c: 5.7%

Kreatinin: 0.9 mg/dL

CRP: 1.2 mg/dL

INR: 1.1

Empfehlungen:
Kardiologische Anschlussheilbehandlung ab 18.03.2024 in Reha-Zentrum Bad Nauheim

Weiterführung der dualen Plättchenhemmung (ASS + Ticagrelor) für 12 Monate

Regelmäßige Kontrolle beim Hausarzt (Blutdruck, Lipide, EKG)

Teilnahme an strukturiertem Rauchentwöhnungsprogramm

Kontrolltermin in unserer Ambulanz am 20.04.2024, 09:30 Uhr

Unterschrift:
Dr. med. Clara Hoffmann
Oberärztin Kardiologie
Musterklinik Berlin
Fax: 030-987654321
E-Mail: clara.hoffmann@musterklinik.de
}`
  }
];

// Połącz krótkie i długie teksty do jednej tablicy
const allTestData = [...longDocuments];

// Główna funkcja testu
export default function () {
  // Wybierz losowe dane z tablicy allTestData
  const dataIndex = Math.floor(Math.random() * allTestData.length);
  const payload = JSON.stringify(allTestData[dataIndex]);
  
  // Ustaw nagłówki HTTP
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  // Wyślij żądanie POST do endpointu anonimizacji
  const response = http.post('http://192.168.0.20:8000/anonymize', payload, params);

  // Sprawdź, czy odpowiedź jest poprawna
  check(response, {     
    'status is 200': (r) => r.status === 200,
    'response has anonymized_text': (r) => JSON.parse(r.body).hasOwnProperty('anonymized_text'),
  });
  
  // Opcjonalnie możesz dodać krótkie opóźnienie między żądaniami
  sleep(2); // 100ms pauzy między żądaniami - odkomentuj, jeśli chcesz spowolnić test
}
FHIR Anonymization API 

Documentation
1. Product Overview
The FHIR Anonymization API is a specialized solution designed to anonymize sensitive patient data in compliance with GDPR regulations, particularly in Germany. It ensures that identifiable health information is securely transformed into non-identifiable data before further processing, analysis, or sharing.
Key Features:
Full compliance with GDPR (Regulation (EU) 2016/679) and BDSG (Bundesdatenschutzgesetz – German Federal Data Protection Act).
Secure anonymization of personal health data based on the FHIR (Fast Healthcare Interoperability Resources) standard.
RESTful API for easy integration with existing healthcare systems.
De-anonymization feature for authorized entities.
Deployable as a Dockerized Spring Boot application.
2. Fields Subject to Anonymization
The following FHIR fields are anonymized to comply with GDPR and BDSG:
Category
FHIR Fields
Legal Basis
Personal Identifiers
Patient.identifier, Practitioner.identifier, RelatedPerson.identifier
GDPR Art. 9(1), BDSG §22(1)
Demographic Data
Patient.name, Patient.telecom, Patient.gender, Patient.birthDate, Patient.address, Patient.photo
GDPR Art. 9(1), Recital 26, BDSG §22
Employment & Relationships
Patient.contact, Patient.communication, RelatedPerson
GDPR Art. 9(1), BDSG §22
Financial & Insurance Data
Coverage.subscriber, Coverage.beneficiary, Claim.patient
GDPR Art. 9(1), BDSG §22
Clinical Information
Observation.subject, Procedure.subject, DiagnosticReport.subject
GDPR Art. 9(1), Recital 26

3. API Documentation
Base URL:
http://localhost:8080/api
3.1 Anonymization Endpoint
Request:
POST /api/anonymize
Headers:
{
  "Content-Type": "application/json"
}

Body Example:
{
  "resourceType": "Patient",
  "id": "patient-12345",
  "name": [{ "family": "Müller", "given": ["Hans"] }],
  "birthDate": "1978-09-23",
  "telecom": [{ "system": "phone", "value": "+49 40 1234567" }]
}

Response:
{
  "resourceType": "Patient",
  "id": "anon-patient",
  "name": [{ "family": "XXX", "given": ["XXX"] }],
  "birthDate": "XXXX-XX-XX",
  "telecom": []
}










3.2 De-anonymization Endpoint
Request:
POST /api/deanonymize
Headers:
{
  "Content-Type": "application/json"
}

Body Example:
{
  "id": "anon-patient"
}

Response:
{
  "id": "patient-12345"
}


4. System Requirements
Minimum Hardware Requirements:
CPU: 2 vCPUs
RAM: 4GB
Storage: 10GB free disk space
Network: Internet access for updates
Software Dependencies:
Java 17 (OpenJDK)
Spring Boot 3.2.0
Maven 3+
Docker 20+
ARX Data Anonymization Library 3.9.0
FHIR Base Library (hapi-fhir-base 6.4.0)

5. Additional Information
The API supports FHIR Bundle objects, allowing batch processing of multiple resources.
Role-based access control (RBAC) should be implemented separately for restricting de-anonymization access.

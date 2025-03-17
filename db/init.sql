CREATE TABLE anonymization (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    anon_id VARCHAR(255) NOT NULL,
    original_value TEXT NOT NULL,
    entity_type VARCHAR(50) NOT NULL
);

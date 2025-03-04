CREATE TABLE anonymized_data (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    resource_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    original_value TEXT NOT NULL,
    anonymized_value TEXT NOT NULL
);

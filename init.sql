-- init.sql
-- Script de inicialización para la base de datos PostgreSQL (si se usa en docker-compose)

CREATE TABLE IF NOT EXISTS scrap_logs (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    tipo_contenido VARCHAR(50),
    total_items INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

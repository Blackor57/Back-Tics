-- init.sql
-- Script de inicialización para la base de datos PostgreSQL

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS scrap_logs (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    tipo_contenido VARCHAR(50),
    total_items INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS snapshots (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    site_title TEXT,
    tipo_contenido VARCHAR(50) NOT NULL,
    total_items INT DEFAULT 0,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshots_url_created ON snapshots(url, created_at DESC);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    current_snapshot_id INT REFERENCES snapshots(id) ON DELETE CASCADE,
    previous_snapshot_id INT REFERENCES snapshots(id) ON DELETE SET NULL,
    resumen_ejecutivo TEXT,
    metricas JSONB,
    diferencias_delta JSONB,
    excel_path TEXT,
    word_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reports_url_created ON analysis_reports(url, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_user_id ON analysis_reports(user_id);

CREATE TABLE IF NOT EXISTS monitored_targets (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    url TEXT NOT NULL,
    dias_duracion INT DEFAULT 3,
    frecuencia_horas INT DEFAULT 12,
    fecha_inicio TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMP WITH TIME ZONE NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    notificar_email BOOLEAN DEFAULT TRUE,
    ultimo_chequeo TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_monitored_targets_user_id ON monitored_targets(user_id);
CREATE INDEX IF NOT EXISTS idx_monitored_targets_activo ON monitored_targets(activo);




-- init.sql
-- Script de inicialización para la base de datos PostgreSQL

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
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

CREATE TABLE IF NOT EXISTS agent_events (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    tipo_evento VARCHAR(80) DEFAULT 'evento_generico',
    titulo VARCHAR(300),
    descripcion TEXT,
    url_fuente TEXT,
    nivel_prioridad VARCHAR(20),
    canal VARCHAR(40) DEFAULT 'sistema',
    razon_ia TEXT,
    metadatos JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_events_created ON agent_events(created_at DESC);

-- ================================================================
-- ESQUEMA CHATBOT RAG (SIMAP IA SEMÁNTICA)
-- Tablas normalizadas para que el chatbot responda sobre los datos
-- almacenados: páginas monitoreadas, cambios detectados, alertas y
-- embeddings pgvector para búsqueda semántica.
-- ================================================================

-- Requiere la extensión vector (pgvector) para VECTOR(768)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pages (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    nombre TEXT,
    ultima_revision TIMESTAMPTZ,
    estado VARCHAR(20) NOT NULL DEFAULT 'activa',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
CREATE INDEX IF NOT EXISTS idx_pages_estado ON pages(estado);

CREATE TABLE IF NOT EXISTS changes (
    id SERIAL PRIMARY KEY,
    page_id INT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    fecha TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resumen TEXT,
    contenido_diff TEXT,
    hash TEXT UNIQUE,
    tipo VARCHAR(30) NOT NULL DEFAULT 'cambio'
);

CREATE INDEX IF NOT EXISTS idx_changes_page_fecha ON changes(page_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_changes_fecha ON changes(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_changes_hash ON changes(hash);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    page_id INT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    tipo VARCHAR(50) NOT NULL DEFAULT 'cambio_detectado',
    severidad VARCHAR(20) NOT NULL DEFAULT 'media',
    fecha TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_page_fecha ON alerts(page_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_severidad ON alerts(severidad);
CREATE INDEX IF NOT EXISTS idx_alerts_fecha ON alerts(fecha DESC);

CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    change_id INT NOT NULL REFERENCES changes(id) ON DELETE CASCADE,
    vector vector(768) NOT NULL,
    contenido TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_embeddings_change ON embeddings(change_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING hnsw (vector vector_cosine_ops);




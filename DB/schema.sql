-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    provider TEXT,
    endpoint TEXT,
    capabilities TEXT[],
    tags TEXT[],
    auth_required BOOLEAN DEFAULT FALSE,
    auth_method TEXT,
    auth_docs TEXT,
    trust_verified BOOLEAN DEFAULT FALSE,
    trust_popularity FLOAT DEFAULT 0.0,
    trust_source TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE tools (
    id SERIAL PRIMARY KEY,
    agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    input_schema JSONB,
    output_schema JSONB
);

CREATE TABLE agent_embeddings (
    agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
    embedding VECTOR(1536),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (agent_id)
);

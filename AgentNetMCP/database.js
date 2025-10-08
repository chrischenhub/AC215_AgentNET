const { Pool } = require('pg');
const path = require('path');

class Database {
  constructor() {
    this.pool = null;
    this.init();
  }

  init() {
    // Load environment variables
    require('dotenv').config();
    
    const config = {
      host: process.env.DB_HOST || 'localhost',
      port: process.env.DB_PORT || 5433,
      database: process.env.DB_NAME || 'agentnet',
      user: process.env.DB_USER || 'postgres',
      password: process.env.DB_PASSWORD || 'mySecurePassword123',
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    };

    this.pool = new Pool(config);
    
    this.pool.on('error', (err) => {
      console.error('Unexpected error on idle client', err);
    });
  }

  async query(text, params) {
    const client = await this.pool.connect();
    try {
      const result = await client.query(text, params);
      return result;
    } finally {
      client.release();
    }
  }

  async searchAgents(query, limit = 10) {
    const searchQuery = `
      SELECT 
        a.id,
        a.name,
        a.description,
        a.provider,
        a.endpoint,
        a.capabilities,
        a.tags,
        a.auth_required,
        a.auth_method,
        a.auth_docs,
        a.trust_verified,
        a.trust_popularity,
        a.trust_source,
        a.created_at
      FROM agents a
      WHERE 
        a.name ILIKE $1 OR 
        a.description ILIKE $1 OR 
        a.provider ILIKE $1 OR
        EXISTS (
          SELECT 1 FROM unnest(a.capabilities) AS cap 
          WHERE cap ILIKE $1
        ) OR
        EXISTS (
          SELECT 1 FROM unnest(a.tags) AS tag 
          WHERE tag ILIKE $1
        )
      ORDER BY a.trust_popularity DESC, a.created_at DESC
      LIMIT $2;
    `;
    
    const searchTerm = `%${query}%`;
    const result = await this.query(searchQuery, [searchTerm, limit]);
    return result.rows;
  }

  async getAgentById(agentId) {
    const query = `
      SELECT 
        a.*,
        json_agg(
          json_build_object(
            'name', t.name,
            'description', t.description,
            'input_schema', t.input_schema,
            'output_schema', t.output_schema
          )
        ) FILTER (WHERE t.name IS NOT NULL) as tools
      FROM agents a
      LEFT JOIN tools t ON a.id = t.agent_id
      WHERE a.id = $1
      GROUP BY a.id;
    `;
    
    const result = await this.query(query, [agentId]);
    return result.rows[0] || null;
  }

  async getAllAgents(limit = 50, offset = 0) {
    const query = `
      SELECT 
        a.id,
        a.name,
        a.description,
        a.provider,
        a.endpoint,
        a.capabilities,
        a.tags,
        a.auth_required,
        a.auth_method,
        a.trust_verified,
        a.trust_popularity,
        a.created_at,
        COUNT(t.id) as tool_count
      FROM agents a
      LEFT JOIN tools t ON a.id = t.agent_id
      GROUP BY a.id
      ORDER BY a.trust_popularity DESC, a.created_at DESC
      LIMIT $1 OFFSET $2;
    `;
    
    const result = await this.query(query, [limit, offset]);
    return result.rows;
  }

  async searchByCapability(capability, limit = 10) {
    const query = `
      SELECT 
        a.id,
        a.name,
        a.description,
        a.provider,
        a.endpoint,
        a.capabilities,
        a.tags,
        a.auth_required,
        a.trust_verified,
        a.trust_popularity
      FROM agents a
      WHERE $1 = ANY(a.capabilities)
      ORDER BY a.trust_popularity DESC
      LIMIT $2;
    `;
    
    const result = await this.query(query, [capability, limit]);
    return result.rows;
  }

  async searchByTag(tag, limit = 10) {
    const query = `
      SELECT 
        a.id,
        a.name,
        a.description,
        a.provider,
        a.endpoint,
        a.capabilities,
        a.tags,
        a.auth_required,
        a.trust_verified,
        a.trust_popularity
      FROM agents a
      WHERE $1 = ANY(a.tags)
      ORDER BY a.trust_popularity DESC
      LIMIT $2;
    `;
    
    const result = await this.query(query, [tag, limit]);
    return result.rows;
  }

  async semanticSearch(query, k = 3) {
    return new Promise((resolve, reject) => {
      const { spawn } = require('child_process');
      const path = require('path');
      
      const scriptPath = path.join(__dirname, 'vector_search.py');
      const pythonProcess = spawn('python3', [scriptPath, query, '--k', k.toString(), '--json']);
      
      let stdout = '';
      let stderr = '';
      
      pythonProcess.stdout.on('data', (data) => {
        stdout += data.toString();
      });
      
      pythonProcess.stderr.on('data', (data) => {
        stderr += data.toString();
      });
      
      pythonProcess.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Python script failed with code ${code}: ${stderr}`));
          return;
        }
        
        try {
          const results = JSON.parse(stdout);
          resolve(results);
        } catch (parseError) {
          reject(new Error(`Failed to parse Python script output: ${parseError.message}`));
        }
      });
      
      pythonProcess.on('error', (error) => {
        reject(new Error(`Failed to start Python script: ${error.message}`));
      });
    });
  }

  async close() {
    if (this.pool) {
      await this.pool.end();
    }
  }
}

module.exports = Database;

#!/usr/bin/env node
/**
 * Script to populate the database with sample data
 */

const Database = require('./database.js');
const fs = require('fs');
const path = require('path');

async function populateDatabase() {
  console.log('📊 Populating AgentNet database...\n');
  
  const db = new Database();
  
  try {
    // Read the agents data
    const agentsPath = path.join(__dirname, '..', 'Data', 'Agents.json');
    const data = JSON.parse(fs.readFileSync(agentsPath, 'utf8'));
    
    const agent = data.agent;
    const tools = data.tools;
    
    console.log(`Inserting agent: ${agent.name}`);
    
    // Insert agent
    await db.query(`
      INSERT INTO agents (id, type, name, description, provider, endpoint, capabilities, tags, auth_required, auth_method, auth_docs, trust_verified, trust_popularity, trust_source, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
    `, [
      agent.id,
      agent.type,
      agent.name,
      agent.description,
      agent.provider,
      agent.endpoint,
      agent.capabilities,
      agent.tags,
      agent.auth_required,
      agent.auth_method,
      agent.auth_docs,
      agent.trust_verified,
      agent.trust_popularity,
      agent.trust_source,
      agent.created_at
    ]);
    
    console.log(`✅ Inserted agent: ${agent.name}`);
    
    // Insert tools
    console.log(`\nInserting ${tools.length} tools...`);
    for (const tool of tools) {
      await db.query(`
        INSERT INTO tools (agent_id, name, description, input_schema, output_schema)
        VALUES ($1, $2, $3, $4, $5)
      `, [
        tool.agent_id,
        tool.name,
        tool.description,
        JSON.stringify(tool.input_schema),
        JSON.stringify(tool.output_schema)
      ]);
      console.log(`  ✅ ${tool.name}`);
    }
    
    console.log('\n🎉 Database populated successfully!');
    
    // Verify the data
    const agentCount = await db.query('SELECT COUNT(*) as count FROM agents');
    const toolCount = await db.query('SELECT COUNT(*) as count FROM tools');
    
    console.log(`\n📊 Database now contains:`);
    console.log(`  - ${agentCount.rows[0].count} agents`);
    console.log(`  - ${toolCount.rows[0].count} tools`);
    
  } catch (error) {
    console.error('❌ Error populating database:', error.message);
  } finally {
    await db.close();
  }
}

if (require.main === module) {
  populateDatabase().catch(console.error);
}

module.exports = { populateDatabase };

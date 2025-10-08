#!/usr/bin/env node
/**
 * Test script to verify AgentNet MCP database integration
 */

const Database = require('./database.js');

async function testDatabaseConnection() {
  console.log('🧪 Testing AgentNet MCP Database Integration\n');
  
  const db = new Database();
  
  try {
    // Test basic connection
    console.log('1. Testing database connection...');
    const testQuery = await db.query('SELECT NOW() as current_time');
    console.log(`   ✅ Connected to database at: ${testQuery.rows[0].current_time}`);
    
    // Test agents table exists
    console.log('\n2. Testing agents table...');
    const agentsCount = await db.query('SELECT COUNT(*) as count FROM agents');
    console.log(`   ✅ Found ${agentsCount.rows[0].count} agents in database`);
    
    // Test search functionality
    console.log('\n3. Testing search functionality...');
    const searchResults = await db.searchAgents('notion', 5);
    console.log(`   ✅ Search for 'notion' returned ${searchResults.length} results`);
    
    if (searchResults.length > 0) {
      console.log(`   📋 First result: ${searchResults[0].name} by ${searchResults[0].provider}`);
    }
    
    // Test get agent by ID
    console.log('\n4. Testing get agent by ID...');
    if (searchResults.length > 0) {
      const agent = await db.getAgentById(searchResults[0].id);
      if (agent) {
        console.log(`   ✅ Retrieved agent: ${agent.name}`);
        console.log(`   📋 Tools count: ${agent.tools ? agent.tools.length : 0}`);
      }
    }
    
    // Test list agents
    console.log('\n5. Testing list agents...');
    const allAgents = await db.getAllAgents(10, 0);
    console.log(`   ✅ Listed ${allAgents.length} agents`);
    
    // Test search by capability
    console.log('\n6. Testing search by capability...');
    const capabilityResults = await db.searchByCapability('search', 3);
    console.log(`   ✅ Found ${capabilityResults.length} agents with 'search' capability`);
    
    // Test search by tag
    console.log('\n7. Testing search by tag...');
    const tagResults = await db.searchByTag('mcp', 3);
    console.log(`   ✅ Found ${tagResults.length} agents with 'mcp' tag`);
    
    console.log('\n🎉 All database tests passed!');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    console.error('   Make sure:');
    console.error('   1. PostgreSQL is running');
    console.error('   2. Database is created and schema is loaded');
    console.error('   3. Environment variables are set correctly');
    console.error('   4. Some data has been ingested into the database');
  } finally {
    await db.close();
  }
}

async function testSemanticSearch() {
  console.log('\n🔍 Testing semantic search integration...');
  
  const db = new Database();
  
  try {
    // Test semantic search
    const semanticResults = await db.semanticSearch('productivity tools', 2);
    console.log(`   ✅ Semantic search returned ${semanticResults.length} results`);
    
    if (semanticResults.length > 0) {
      console.log(`   📋 Top result: ${semanticResults[0].name} (score: ${semanticResults[0].similarity_score.toFixed(3)})`);
    }
    
    console.log('🎉 Semantic search test passed!');
    
  } catch (error) {
    console.error('❌ Semantic search test failed:', error.message);
    console.error('   Make sure:');
    console.error('   1. Python environment is set up');
    console.error('   2. Chroma vector store is populated');
    console.error('   3. OpenAI API key is configured');
  } finally {
    await db.close();
  }
}

async function main() {
  await testDatabaseConnection();
  await testSemanticSearch();
  
  console.log('\n✨ Integration test completed!');
  console.log('\nNext steps:');
  console.log('1. Start the MCP server: node mcp-server.js');
  console.log('2. Configure your MCP client to use the server');
  console.log('3. Test the MCP tools from your client');
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { testDatabaseConnection, testSemanticSearch };


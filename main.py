from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from typing import List, Optional

app = FastAPI()

# --- Database settings ---
DB_NAME = "agentnet"
DB_USER = "postgres"
DB_PASS = "chris"   # <- replace this
DB_HOST = "localhost"
DB_PORT = "5432"

def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

# --- Pydantic Models ---
class Agent(BaseModel):
    id: str
    type: str
    name: str
    description: Optional[str] = None
    provider: Optional[str] = None
    endpoint: Optional[str] = None
    capabilities: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    auth_required: bool = False

class Tool(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None

# --- Routes ---
@app.get("/")
def root():
    return {"message": "AgentNET API is running 🚀"}

# === AGENTS ===
@app.get("/agents")
def get_agents():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, type, name, provider FROM agents;")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {"id": r[0], "type": r[1], "name": r[2], "provider": r[3]}
        for r in rows
    ]

@app.post("/agents")
def create_agent(agent: Agent):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO agents (id, type, name, description, provider, endpoint, capabilities, tags, auth_required)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            agent.id, agent.type, agent.name, agent.description, agent.provider,
            agent.endpoint, agent.capabilities, agent.tags, agent.auth_required
        ))
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

    return {"message": f"Agent {agent.id} created successfully"}

# === TOOLS ===
@app.get("/agents/{agent_id}/tools")
def get_tools(agent_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM tools WHERE agent_id = %s", (agent_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [{"id": r[0], "name": r[1], "description": r[2]} for r in rows]

@app.post("/agents/{agent_id}/tools")
def create_tool(agent_id: str, tool: Tool):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO tools (agent_id, name, description, input_schema, output_schema)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            agent_id, tool.name, tool.description, tool.input_schema, tool.output_schema
        ))
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

    return {"message": f"Tool '{tool.name}' added to agent {agent_id}"}

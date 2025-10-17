# Virtual Machine Set Up

# AgentNet RAG search + MCP Execution
## Quickstart
1. Copy the example environment file and fill in your keys:
   ```bash
   cp .env.example .env
   ```

   ```.env
    OPENAI_API_KEY = 
    SMITHERY_API_KEY = # go to https://smithery.ai/ crreate an account and retrieve the API key
   ```

   In [smithery AI](https://smithery.ai/), search for Notion and complete the configuration of Notion credential. 

2. create a folder `secrets` and add the service-account.json with google cloud credential to the folder

3. create a folder `GCB` to store the ChromaDB mounted from google cloud bucket.


2. Build the image and start the stack (Postgres + dev container):
   ```bash
   docker compose up -d --build
   ```

3. Execute the workflow RAG search + MCP
    ```
    docker compose exec agentnet python notion_agent.py "What do you want to do"
    ```

## Data Pipeline

`parentPageExtract.py`: discover and scrape MCP parent pages to build a list of MCP servers from smithery AI webpage (id, discovery_url, minimal metadata) and write the result to servers.csv

`childpageextract.py`: read servers.csv, visit each server entry to extract full server details (tools, parameters, descriptions, endpoints, provider, tags), normalize fields, and write the result to servers_full.csv

`mcp_to_json.py`: convert servers_full.csv into a canonical agents.json (serialize rows into the expected JSON schema / `mcp` array or top-level `agent` objects), validate required fields, and write agents.json

`RAG.py`: load agents.json, chunk content **by tool** (one chunk per tool including tool_name, tool_description, parameters, plus agent metadata), compute embeddings for each chunk, add texts+metadata to a Chroma collection persisted at DB/chroma_store, call persist(), and upload the DB/chroma_store directory to the configured Google Cloud Storage bucket

## RAG -> MCP workflow (Ex. Notion)
1. `main.py`: User enter a question.For example, "I want to create a  "I want to create a SQL study plan using a notetaking tool."

2. `RAG.py`: mount the ChromaDB stored in google cloud bucket to the docker container and retrieve the Top 3 most relevant MCP servers that meet the user's request

Results: 
![alt text](Image/image1.png)

3. `notion_agent.py`: receive the MCP link of the MCP server that the user pick and build the connection. The link is provided by smithery AI 

4. `main.py`: Prompt the user for a more detailed instruction and send to the MCP server of Notion to execute. 

5. Go to the Notion and found that SQL studyn plan created successfully.
Results:
![alt text](Image/image2.png)

Results from Notion page:
![alt text](Image/image3.png)


🚀 ChatXWiki

AI-powered knowledge assistant for XWiki using RAG + Weaviate + MCP + FastAPI

ChatXWiki is a Retrieval-Augmented Generation (RAG) system that automatically indexes your XWiki pages, stores their embeddings inside Weaviate, and exposes an intelligent chat assistant accessible from any XWiki page.

It combines:

MCP Server → exposes retrieval tools

MCP Client wrapped inside FastAPI → handles RAG and LLM reasoning

Weaviate Vector DB → stores chunk embeddings

XWiki Ingestion Pipeline → extracts, chunks, embeds, and stores all XWiki page content

Floating Chat Widget → a JavaScript UI embedded into XWiki

Docker Compose → reproducible deployment of all components

📌 Features

🔍 Semantic search across all XWiki pages

📚 Fully automated vector ingestion and chunk generation

🤖 RAG-powered LLM answering using OpenAI GPT models

🧩 MCP Server tool: retrieve_top_k_chunks

🌐 FastAPI wrapper exposes /ingest and /rag_query endpoints

💬 Chat widget floats on every XWiki page

👑 Admin-only “Rebuild Knowledge Base” button via Velocity script

🐳 Single-command deployment with Docker Compose

🏗️ Architecture Overview

Below is your architecture diagram (replace with your actual .jpg):

![ChatXWiki Architecture](./architecture.jpg)

📁 Project Structure
project-root/
│
├── docker-compose.yml
├── README.md
│
├── mcp/
│   ├── services.sh
│   ├── Dockerfile
│   ├── ingest_wiki_pages.py        # XWiki → Weaviate ingestion (FastAPI)
│   ├── mcp_client.py               # MCP-based RAG client (FastAPI)
│   ├── mcp_server.py               # MCP Server exposing retrieval tool
│   ├── requirements.txt
│   ├── .env
│
└── xwiki_integration/
    ├── ChatXWiki_UI.js             # Floating chat widget JS
    └── injest_knowledgebase_button.vm   # Velocity script for admin-only button

⚙️ Components
🔹 1. MCP Server

Implements retrieve_top_k_chunks, which:

embeds query using OpenAI

queries Weaviate for nearest neighbors

returns structured JSON with top-K chunks

🔹 2. MCP Client + FastAPI

Runs a FastAPI server exposing:

Endpoint	Description
POST /rag_query	Runs full RAG pipeline: retrieval → LLM → answer
POST /ingest	Triggers XWiki → Weaviate ingestion pipeline

Internally:

connects to MCP server via SSE

sends user queries to MCP tools

builds context & performs RAG using LangChain OpenAI

🔹 3. Weaviate Vector Database

Stores embedded XWiki chunks in a collection:

DocumentChunk
 ├─ content
 ├─ parent_id
 ├─ fullName
 ├─ title
 ├─ chunk_index
 ├─ url
 ├─ creator
 └─ vector (embedding)

🔹 4. XWiki Ingestion System

ingest_wiki_pages.py:

Recursively crawls all spaces (Main, Sandbox, etc.)

Fetches each page’s WebHome JSON

Cleans and extracts content

Chunks content via LangChain

Generates embeddings using OpenAI

Upserts into Weaviate using v4 API

Triggered by:

FastAPI endpoint (/ingest)

Admin-only button inside XWiki

🔹 5. Floating Chat Widget (JavaScript)

ChatXWiki_UI.js injects:

A floating chat window

Input field + message history

Calls POST http://localhost:9100/rag_query

Lives inside XWiki → Administration → Look & Feel → JavaScript Extension.

🔹 6. Velocity Script

injest_knowledgebase_button.vm added to an admin-only page:

Shows a button "Rebuild Knowledge Base"

Sends POST request to FastAPI /ingest

Updates the entire Weaviate collection

🚀 Running ChatXWiki
Step 1 — Start all services

From the project root:

docker compose up -d


This launches:

XWiki

Weaviate

MCP server

FastAPI RAG service

Step 2 — Install & configure XWiki

Visit:

http://localhost:8080


Complete:

Setup Wizard

Admin user creation

Standard XWiki Flavor installation

Step 3 — Add Admin-Only Knowledge Rebuild Button

Create an admin-only page and paste:

(injest_knowledgebase_button.vm contents)


This button triggers /ingest to rebuild embeddings.

Step 4 — Add Floating Chat Widget

Open:

XWiki → Administration → Look & Feel → JavaScript Extension

Create a new extension and paste:

ChatXWiki_UI.js contents


Settings:

Use this extension on this wiki

Parse content: No

Caching policy: Long

Save → Chat widget appears on all pages.

Step 5 — Start Chatting

Type into the floating chatbox — queries will:

Chat Widget → FastAPI → MCP Client → MCP Server → Weaviate → LLM → Chat Widget

🧪 Testing the APIs
Trigger ingestion
curl -X POST http://localhost:9000/ingest

Ask a RAG question
curl -X POST http://localhost:9100/rag_query \
     -H "Content-Type: application/json" \
     -d '{"query": "what is our lab policy?"}'

🔐 Environment Variables

Example .env:

OPENAI_API_KEY=yourkey
XWIKI_BASE_URL=http://xwiki:8080
XWIKI_WIKI=xwiki
WEAVIATE_URL=http://weaviate:8080
WEAVIATE_API_KEY=
EMBEDDING_MODEL_NAME=text-embedding-3-small

🤝 Contributing

Pull requests are welcome.
Please open an issue first to discuss major changes.

📜 License

MIT License
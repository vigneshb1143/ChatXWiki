# 🚀 ChatXWiki

**AI-powered knowledge assistant for XWiki using RAG + Weaviate + MCP + FastAPI**

ChatXWiki is a Retrieval-Augmented Generation (RAG) system that automatically indexes your XWiki pages, stores their embeddings inside Weaviate database, and exposes an intelligent chat assistant accessible from any XWiki page. The RAG pipeline retrieves the most relevant document chunks from your XWiki pages and feeds them into the LLM as context before generating a response. By grounding the model in your own documentation, ChatXWiki ensures that responses are accurate, context-aware, and tailored to your organization’s knowledge ecosystem.

It combines:

- **MCP Server** → exposes retrieval tools  
- **MCP Client wrapped with FastAPI** → handles RAG + LLM reasoning  
- **Weaviate Vector DB** → stores embedded document chunks  
- **XWiki Ingestion Pipeline** → extracts, chunks, embeds, stores all XWiki content  
- **Floating Chat Widget** → JavaScript UI embedded directly into XWiki  
- **Docker Compose** → reproducible deployment of all services  

---

## 📌 Features

- 🔍 Semantic search across all XWiki pages  
- 📚 Fully automated vector ingestion & chunk generation  
- 🤖 RAG-powered LLM answering using OpenAI GPT models  
- 🧩 MCP Server tool: `retrieve_top_k_chunks`  
- 🌐 FastAPI endpoints: `/ingest` and `/rag_query`  
- 💬 Floating chat widget appears on every XWiki page  
- 👑 Admin-only "Rebuild Knowledge Base" button (Velocity script)  
- 🐳 One-command deployment with Docker Compose  

---

## 🏗️ Architecture Overview

![ChatXWiki Architecture](images/Project_Architecture.jpg)

---

## 📁 Project Structure
```text
project-root/
│
├── docker-compose.yml
├── README.md
│
├── mcp/
│ ├── services.sh
│ ├── Dockerfile
│ ├── ingest_wiki_pages.py # XWiki → Weaviate ingestion (FastAPI)
│ ├── mcp_server.py # MCP Server exposing retrieval tool
│ ├── mcp_client.py # MCP-based RAG client (FastAPI)
│ ├── requirements.txt
│ ├── .env
│
└── xwiki_integration/
├── ChatXWiki_UI.js # Floating chat widget
└── injest_knowledgebase_button.vm # Velocity script for admin-only button
```

---

## ⚙️ Components

### 🔹 1. MCP Server

Implements the main retrieval tool: `retrieve_top_k_chunks`

This tool:

- Embeds the user query using OpenAI
- Searches Weaviate for nearest neighbors
- Returns structured JSON containing the top-K chunks

---

### 🔹 2. MCP Client + FastAPI

Runs a FastAPI service that exposes the below API:

| Endpoint         | Description |
|------------------|-------------|
| **POST /rag_query** | Runs full RAG pipeline → retrieval + LLM reasoning |

Internally, the FastAPI MCP client:

- Connects to MCP server via **SSE**
- Calls the MCP server tool `retrieve_top_k_chunks`
- Builds context for RAG
- Uses **LangChain + OpenAI GPT** model to generate the final answer

---

### 🔹 3. XWiki Ingestion System

`ingest_wiki_pages.py`:

1. Crawls all XWiki spaces  
2. Loads each page’s `WebHome` metadata + wiki content  
3. Cleans & extracts text  
4. Splits into RAG chunks (LangChain)  
5. Generates embeddings with OpenAI  
6. Writes into Weaviate vector database (v4 API)

Triggered by:

- FastAPI endpoint `/ingest`
- Admin-only button inside XWiki

---

### 🔹 4. Weaviate Vector Database

Stores embedded XWiki chunks in collection **DocumentChunk**:

- `content`
- `parent_id`
- `fullName`
- `title`
- `chunk_index`
- `url`
- `creator`
- `last_modified`
- `vector` (OpenAI embedding)

---

### 🔹 5. Floating Chat Widget (JavaScript)

`ChatXWiki_UI.js` adds:

- A draggable floating chat window  
- Persistent UI across all pages  
- Calls FastAPI at:
POST /rag_query

Added via:
XWiki → Administration → Look & Feel → JavaScript Extension

---

### 🔹 6. Velocity Script (Admin Button)

`injest_knowledgebase_button.vm` provides:

- A button: **Rebuild Knowledge Base**
- Sends POST request to FastAPI `/ingest`
- Rebuilds all embeddings from XWiki → Weaviate

---

## 🚀 Running ChatXWiki

### **Step 1: Start all services**

docker compose up -d

This starts:

- XWiki

- PostgreSQL

- Weaviate

- MCP Server

- FastAPI RAG Service

- FastAPI ingestion Service

### **Step 2: Install & configure XWiki**

Visit:

http://localhost:8080

Complete:

- Setup Wizard

- Create admin user

- Install Standard XWiki Flavor

### **Step 3: Add Admin-Only Knowledge Rebuild Button**

1. Create a new **admin-only page** in XWiki.

2. Open the page and click **Edit → Source** mode.

3. Paste the entire contents of `injest_knowledgebase_button.vm` into the editor and save the page.

This will add a “Rebuild Knowledge Base” button that only administrators can see. When clicked, it triggers the `/ingest` API endpoint and rebuilds the ChatXWiki vector index inside Weaviate.

### **Step 4: Add Floating Chat Widget**

Go to:
`XWiki → Administration → Look & Feel → JavaScript Extension`

Add a new extension:

- Paste the contents of `ChatXWiki_UI.js`

- Select these options: Use this extension → On this wiki; Parse content → No; Caching → Long

- Click Save → Chat widget appears globally.

### **Step 5: Start Chatting!**

User flow:
Chat Widget 
    → FastAPI 
        → MCP Client 
            → MCP Server 
                → Weaviate 
            → LLM (OpenAI)
        → Response back to UI

## 🧪 **Testing the APIs**
Trigger ingestion
`curl -X POST http://localhost:9000/ingest`

## 🔐 **Environment Variables**

Example .env:
```
OPENAI_API_KEY=insert_your_key_here
OPENAI_EMBEDDING_MODEL=${OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}
OPENAI_LLM=${OPENAI_LLM:-gpt-5.1}
MCP_AUTH_TOKEN=${MCP_AUTH_TOKEN:-supersecrettoken}
WEAVIATE_URL=http://weaviate:8000
WEAVIATE_GRPC_PORT=50051
WEAVIATE_CLASS=${WEAVIATE_CLASS:-DocumentChunk}
MCP_SERVER_PORT=8050
```
## 🤝 **Contributing**
Pull requests are welcome!
For major changes, please open an issue first.

## 📜 **License**
MIT License

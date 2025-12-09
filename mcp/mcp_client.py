import asyncio
import os
import json
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Dict, Any, List

from mcp import ClientSession
from mcp.client.sse import sse_client

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

OPENAI_LLM = os.getenv("OPENAI_LLM", "gpt-4.1")
MCP_SERVER_PORT = os.getenv("MCP_SERVER_PORT")
MCP_SERVER_SSE_URL = "http://localhost:" + MCP_SERVER_PORT + "/sse" #change this accordingly  

# ------------------------------------------------------------
# Connect to MCP Server 
# ------------------------------------------------------------

class MCPRAGClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self.read = None
        self.write = None

    async def connect(self):
        """
        Connect to MCP server using SSE
        """
        transport = await self.exit_stack.enter_async_context(
            sse_client(MCP_SERVER_SSE_URL)
        )
        self.read, self.write = transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.read, self.write)
        )

        await self.session.initialize()

        tools = await self.session.list_tools()
        print("Connected to MCP server. Tools available:")
        for tool in tools.tools:
            print(f" - {tool.name}: {tool.description}")

    async def close(self):
        await self.exit_stack.aclose()


# ------------------------------------------------------------
# Call MCP Tool for Retrieval
# ------------------------------------------------------------

async def call_mcp_retrieval(session: ClientSession, query: str, top_k: int = 5):
    """
    Calls the MCP tool 'retrieve_top_k_chunks'.
    """
    result = await session.call_tool(
        "retrieve_top_k_chunks",
        {"user_query": query, "top_k": top_k}
    )

    # MCP response comes wrapped. Unwrap the content:
    # print('result',result)
    text = result.content[0].text
    return json.loads(text)["top_chunks"]

# ------------------------------------------------------------
# Build Context for RAG
# ------------------------------------------------------------

def build_context(chunks: List[Dict[str, Any]]) -> str:
    parts = []
    for i, c in enumerate(chunks):
        parts.append(
            f"[Chunk {c['chunk_index']}] (Score={c['score']:.4f})\n"
            f"Title: {c.get('title')}\n"
            f"URL: {c.get('url')}\n"
            f"Content:\n{c.get('content')}\n"
            f"{'-'*80}"
        )
        if i == 0:
            print('Context k=', parts)
    return "\n".join(parts)


# ------------------------------------------------------------
# LLM RAG Generation
# ------------------------------------------------------------

async def run_rag(query: str, chunks: List[Dict[str, Any]]) -> str:

    context = build_context(chunks)
    # print('>>>>>>>>>>>>>This is the context\n',context, '\n' )
    llm = ChatOpenAI(model=OPENAI_LLM, temperature=0.2)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a helpful assistant. Use ONLY the provided context. "
         "If unsure, say you don't know."),
        ("human",
         "Query:\n{query}\n\nContext:\n{context}\n\nAnswer:")
    ])

    chain = prompt | llm

    resp = await chain.ainvoke({"query": query, "context": context})
    return resp.content

# -----------------------------
# FASTAPI SETUP
# -----------------------------

mcp_rag_client = MCPRAGClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting FastAPI server…")
    await mcp_rag_client.connect()
    yield
    print("Shutting down FastAPI server…")
    await mcp_rag_client.close()

app = FastAPI(title="XWiki RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    top_k: int

@app.post("/rag_query")
async def rag_query(body: QueryRequest):
    try:
        chunks = await call_mcp_retrieval(mcp_rag_client.session, body.query, body.top_k)
        answer = await run_rag(body.query, chunks)
        return {"answer": answer, "chunks_used": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

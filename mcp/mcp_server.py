import os
import typing as t
# import time
# import json
from urllib.parse import urlparse

# FastMCP
from mcp.server.fastmcp import FastMCP

# LangChain embeddings
from langchain_openai import OpenAIEmbeddings

# Weaviate client v4
import weaviate
# from weaviate.classes.init import Auth
import weaviate.classes as wvc

# ---------- Config ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Please set OPENAI_API_KEY in the environment")

OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://weaviate:8000")
WEAVIATE_GRPC_PORT = os.getenv("WEAVIATE_GRPC_PORT", 50051)
WEAVIATE_CLASS = os.getenv("WEAVIATE_CLASS", "DocumentChunk")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "supersecrettoken")
MCP_SERVER_PORT = os.getenv("MCP_SERVER_PORT", 8050)

# ----------------------------
# 1. Connect to Weaviate (v4)
# ----------------------------

def get_weaviate_client():
    """
    Parses the URL and connects using Weaviate v4 syntax.
    """
    parsed = urlparse(WEAVIATE_URL)
    host = parsed.hostname
    port = parsed.port
    # The standard gRPC port for Weaviate is 50051
    # GRPC_PORT = 50051    
    print(f"Connecting to Weaviate at HTTP:{host}:{port} and gRPC:{host}:{WEAVIATE_GRPC_PORT}...")
    # Use connect_to_custom to handle docker container hostnames
    client = weaviate.connect_to_custom(
        http_host=host,
        http_port=port,
        http_secure=(parsed.scheme == "https"),
        grpc_host=host,
        grpc_port=WEAVIATE_GRPC_PORT,
        grpc_secure=(parsed.scheme == "https"),
        # headers={
        #     "X-OpenAI-Api-Key": OPENAI_API_KEY  # Optional: if you want Weaviate to do vectorization directly later
        # }
    )
    assert client.is_ready()
    print("Weaviate connected and ready.")
    return client

# ---------- LangChain embeddings & vectorstore adapter ----------

# ----------------------------
# 2. Embed the query
# ----------------------------

def embed_query(query: str) -> list[float]:
    embedder = OpenAIEmbeddings(
        model=OPENAI_EMBEDDING_MODEL,
        api_key=OPENAI_API_KEY)
    # embed_query returns 1 vector
    return embedder.embed_query(query)

# ----------------------------
# 3. Vector Search (Top k)
# ----------------------------

def query_chunks(query: str, top_k: int):
    client = get_weaviate_client()
    query_vector = embed_query(query)

    collection = client.collections.use(WEAVIATE_CLASS)

    result = collection.query.near_vector(
        near_vector=query_vector,
        limit=top_k,
        return_metadata=wvc.query.MetadataQuery(
            distance=True
        ),
        return_properties=[
            "content",
            "title",
            "url",
            "chunk_index",
            "parent_id"
        ]
    )

    client.close()
    return result.objects  # a list of Weaviate objects


mcp = FastMCP("RAG-MCP-Server", host="0.0.0.0", port=MCP_SERVER_PORT, stateless_http=True,)
print("FastMCP server initialized")


@mcp.tool()
def retrieve_top_k_chunks(user_query: str, top_k: int = 5) -> dict:
    results = query_chunks(user_query, top_k)
    print('I got the following results: ', results)
    formatted = []
    for obj in results:
        formatted.append({
            "chunk_id": obj.uuid,
            "score": obj.metadata.distance,
            "content": obj.properties.get("content"),
            "title": obj.properties.get("title"),
            "url": obj.properties.get("url"),
            "chunk_index": obj.properties.get("chunk_index"),
            "parent_id": obj.properties.get("parent_id")
        })

    return {
        "query": user_query,
        "top_chunks": formatted
    }

if __name__ == "__main__":
    # this block runs the server; when deployed inside Docker this will be the main process
    print(f"Starting FastMCP HTTP server on 0.0.0.0:{MCP_SERVER_PORT}")
    mcp.run(transport="sse")

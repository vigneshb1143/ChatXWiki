from typing import List, Dict, Any, Optional
import os
import re
import time
import uuid
import logging

import requests

# LangChain/OpenAI wrapper (as per user's environment)
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import TokenTextSplitter, RecursiveCharacterTextSplitter
# from bs4 import BeautifulSoup

# Weaviate client and classes
from weaviate import WeaviateClient, auth
from weaviate.connect import ConnectionParams
import weaviate.classes as wvc

# FastAPI for microservice
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ------------------------- Logging -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------- Configuration -------------------------
XWIKI_BASE_URL = os.getenv("XWIKI_BASE_URL", "http://xwiki:8080")
XWIKI_WIKI = os.getenv("XWIKI_WIKI", "xwiki")
XWIKI_USERNAME = os.getenv("XWIKI_USERNAME")
XWIKI_PASSWORD = os.getenv("XWIKI_PASSWORD")
XWIKI_API_TOKEN = os.getenv("XWIKI_API_TOKEN")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://weaviate:8000")
WEAVIATE_GRPC_PORT = 50051
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))

WEAVIATE_CLASS = os.getenv("WEAVIATE_CLASS", "DocumentChunk")
# WEAVIATE_CLASS = "DocumentChunk"

# ------------------------- Requests session -------------------------
session = requests.Session()
session.headers.update({"Accept": "application/json"})
if XWIKI_API_TOKEN:
    session.headers.update({"Authorization": f"Bearer {XWIKI_API_TOKEN}"})
elif XWIKI_USERNAME and XWIKI_PASSWORD:
    session.auth = (XWIKI_USERNAME, XWIKI_PASSWORD)


def clean_wiki_syntax(raw: Optional[str]) -> str:
    """Convert a bit of XWiki wiki syntax into reasonably clean plain text.
    This is heuristic but works well for typical pages.
    """
    if not raw:
        return ""
    text = raw
    # remove box/macro blocks {{...}} including nested content
    text = re.sub(r"\{\{.*?\}\}", " ", text, flags=re.DOTALL)
    # headings: == Heading ==  or === Heading === -> Heading\n
    text = re.sub(r"={2,}\s*(.*?)\s*={2,}", r"\1\n", text)

    # bold/italic markers
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"//(.*?)//", r"\1", text)

    # lists
    text = re.sub(r"^\s*[\*#]\s*", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s*", "- ", text, flags=re.MULTILINE)

    # links like [[text>>Page]] or [[Page]]
    text = re.sub(r"\[\[(.*?)>>.*?\]\]", r"\1", text)
    text = re.sub(r"\[\[(.*?)\]\]", r"\1", text)

    # remove percent blocks and double percent
    text = text.replace("%%", " ")

    # remove remaining wiki tokens like {{/box}} etc
    text = re.sub(r"\{\{|\}\}", " ", text)

    # collapse multiple newlines and whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s{3,}", " ", text)

    return text.strip()


# ------------------------- XWiki fetchers -------------------------
def fetch_all_webhome_links() -> List[Dict[str, str]]:
    """
    Returns list of:
      {
         "name": <space name>,
         "webhome_url": <REST URL to WebHome>,
         "view_url": <browser URL>
      }
    """
    url = f"{XWIKI_BASE_URL}/rest/wikis/{XWIKI_WIKI}/spaces?media=json"
    r = session.get(url)
    r.raise_for_status()

    js = r.json()
    results = []

    for sp in js.get("spaces", []):
        name = sp.get("name")
        view_url = sp.get("xwikiAbsoluteUrl")  # GUI link

        webhome_url = None

        for link in sp.get("links", []):
            if link.get("rel") == "http://www.xwiki.org/rel/home":
                webhome_url = link.get("href")
                break

        if name and webhome_url:
            results.append({
                "name": name,
                "webhome_url": webhome_url,
                "view_url": view_url
            })

    return results

def fetch_webhome_doc(url: str) -> Dict[str, Any]:
    r = session.get(url)
    r.raise_for_status()
    pj = r.json()

    raw_content = pj.get("content", "")
    text = clean_wiki_syntax(raw_content)

    return {
        "page_id": pj.get("id"),
        "fullName": pj.get("fullName"),
        "space": pj.get("space"),
        "title": pj.get("title"),
        "url": pj.get("xwikiAbsoluteUrl") or pj.get("xwikiRelativeUrl"),
        "creator": pj.get("creator"),
        "last_modified": pj.get("modified"),
        "text": text,
        "raw_wiki": raw_content,
    }

def load_documents() -> List[Dict[str, Any]]:
    docs = []

    spaces = fetch_all_webhome_links()
    logger.info(f"Found {len(spaces)} spaces with WebHome pages")

    for sp in spaces:
        name = sp["name"]
        webhome_url = sp["webhome_url"]

        logger.info(f"Fetching WebHome: {name} → {webhome_url}")

        try:
            doc = fetch_webhome_doc(webhome_url)
            docs.append(doc)
        except Exception as e:
            logger.warning(f"Failed to fetch WebHome for {name}: {e}")

    logger.info(f"Loaded {len(docs)} pages from XWiki")
    return docs


# ------------------------- Chunking -------------------------

def chunk_documents(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Token-aware chunking that preserves metadata on each chunk."""
    try:
        # Assumes TokenTextSplitter is compatible with the embedding model's tokenization
        splitter = TokenTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    except Exception:
        # Fallback to character splitter if token splitter fails
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    chunks: List[Dict[str, Any]] = []
    for doc in docs:
        text = doc.get("text", "")
        if not text:
            continue
        parts = splitter.split_text(text)
        for i, part in enumerate(parts):
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "parent_id": doc.get("page_id"),
                "fullName": doc.get("fullName"),
                "space": doc.get("space"),
                "title": doc.get("title"),
                "url": doc.get("url"),
                "creator": doc.get("creator"),
                "last_modified": doc.get("last_modified"),
                "chunk_index": i,
                "content": part,
            })
    logger.info("Created %d chunks", len(chunks))
    return chunks

# ------------------------- Embeddings -------------------------

def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if OPENAI_API_KEY is None:
        raise RuntimeError("OPENAI_API_KEY is not set")

    embedder = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY, model=EMBEDDING_MODEL_NAME)
    texts = [c["content"] for c in chunks]
    vectors: List[List[float]] = []

    # Batch embedding with rate limiting
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        # Using a try/except for robustness against API errors
        try:
            vecs = embedder.embed_documents(batch)
            vectors.extend(vecs)
            time.sleep(0.05) # Small pause to respect rate limits
        except Exception as e:
            logger.error("OpenAI embedding failed for batch starting at index %d: %s", i, e)
            # Decide on strategy: skip batch, or raise
            raise

    for c, v in zip(chunks, vectors):
        c["embedding"] = v

    logger.info("Embedded %d chunks", len(chunks))
    return chunks

# ------------------------- Weaviate helpers -------------------------
def _connect_weaviate() -> WeaviateClient:
    """
    Initializes and returns the Weaviate client using explicit ConnectionParams
    """
    # 1. Prepare Auth Config (using the corrected lowercase 'auth')
    auth_config = auth.api_key(api_key=WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None
    
    # 2. Parse the URL to determine scheme and host/port
    if "://" not in WEAVIATE_URL:
        full_url = "http://" + WEAVIATE_URL 
    else:
        full_url = WEAVIATE_URL

    scheme, host_port = full_url.split("://")
    host, _, port = host_port.partition(":")
    
    # 3. Create ConnectionParams object
    conn_params = ConnectionParams.from_url(
        url=full_url,
        grpc_port=WEAVIATE_GRPC_PORT
        # The client needs the bare host and port for HTTP configuration
        # which from_url attempts to parse, but this is the safest way.
    )

    # 4. Initialize WeaviateClient
    client = WeaviateClient(
        connection_params=conn_params,
        auth_client_secret=auth_config,
    )
    
    try:
        client.is_ready()
        print('Weaviate client ready')  
    except Exception as e:
        logger.error("Weaviate not ready at %s: %s", WEAVIATE_URL, e)
        raise
        
    return client

def _ensure_weaviate_schema(client: WeaviateClient):
    # existing_collection_names = list(client.collections.list_all(simple=False).keys())
    if client.collections.exists(WEAVIATE_CLASS):
        logger.debug("Weaviate collection %s already exists", WEAVIATE_CLASS)
        return
    
    # Define the collection configuration
    logger.info("Creating Weaviate collection: %s", WEAVIATE_CLASS)

    # Define the properties (columns) of the collection
    properties = props = [
        wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="parent_id", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="fullName", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="space", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="url", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="creator", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="last_modified", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="chunk_index", data_type=wvc.config.DataType.INT),
        ]
    vector_cfg = wvc.config.Configure.Vectors.self_provided()
    client.collections.create(
    name=WEAVIATE_CLASS,
    properties=properties,
    vector_config=vector_cfg,
    )
    logger.info("Created new Weaviate collection: %s", WEAVIATE_CLASS)

# ------------------------- Data Ingestion (write_to_vector_db) -------------------------
def write_to_vector_db(chunks_with_embeddings: List[Dict[str, Any]]) -> None:
    """
    Inserts a list of chunks with their embeddings into the Weaviate vector database
    using the v4 `insert_many` method.
    """

    try:
        # 1. Connect and ensure schema
        with _connect_weaviate() as client:
            # Optional; be careful in production
            client.collections.delete_all() #WARNING!!!! 
            _ensure_weaviate_schema(client)
            logger.info("Weaviate client and schema ensured")

            # 2. Get the collection
            collection = client.collections.get(WEAVIATE_CLASS)

            # 3. Prepare DataObjects for insert_many
            data_objects: List[wvc.data.DataObject] = []
            for c in chunks_with_embeddings:
                data_objects.append(
                    wvc.data.DataObject(
                        properties={
                            "content": c.get("content"),
                            "parent_id": c.get("parent_id"),
                            "fullName": c.get("fullName"),
                            "space": c.get("space"),
                            "title": c.get("title"),
                            "url": c.get("url"),
                            "creator": c.get("creator"),
                            "last_modified": str(c.get("last_modified")),
                            "chunk_index": c.get("chunk_index"),
                        },
                        uuid=c.get("chunk_id"),
                        vector=c.get("embedding"),  # same pattern as docs
                    )
                )

            # 4. Perform batch-style insertion with insert_many
            response = collection.data.insert_many(data_objects)
            # `insert_many` returns IDs and Error objects as described in the blog [[Quality-of-life](https://weaviate.io/blog/collections-python-client-preview#quality-of-life-improvements)].

            # Collect errors (if any)
            if response.has_errors:
                errors = response.errors
                logger.warning(
                    "Inserted %d chunks into Weaviate; %d objects had errors.",
                    len(data_objects) - len(errors),
                    len(errors),
                )
                # Log first error for diagnosis
                first_index, first_error = next(iter(errors.items()))
                logger.debug("First insert_many error at index %d: %s", first_index, first_error)
            else:
                logger.info(
                    "Successfully inserted %d chunks into Weaviate class %s.",
                    len(data_objects),
                    WEAVIATE_CLASS,
                )

    except Exception as e:
        logger.error("Failed to write chunks to Weaviate: %s", e)


# ------------------------- Orchestration / FastAPI -------------------------

app = FastAPI()

class IngestResponse(BaseModel):
    docs_loaded: int
    chunks_created: int
    message: str

@app.post("/ingest", response_model=IngestResponse)
def api_ingest():
    try:
        docs = load_documents()
        chunks = chunk_documents(docs)
        chunks = embed_chunks(chunks)
        write_to_vector_db(chunks)
        return IngestResponse(docs_loaded=len(docs), chunks_created=len(chunks), message="Ingestion completed")
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    # Simple run for local testing
    logger.info("Starting full ingest run (CLI)")
    d = load_documents()
    ch = chunk_documents(d)
    ch = embed_chunks(ch)
    write_to_vector_db(ch)
    logger.info("Done")
#!/bin/bash
echo "Starting ingest service..."
uvicorn ingest_wiki_pages:app --host 0.0.0.0 --port 9000 &

echo "Starting MCP server..."
python mcp_server.py &

echo "Waiting for MCP server to become ready..."
# while ! nc -z localhost 8050; do
while ! (echo > /dev/tcp/localhost/8050) 2>/dev/null; do
    sleep 1
done
echo "MCP server is UP!"
sleep 1

echo "Starting MCP client..."
uvicorn mcp_client:app --host 0.0.0.0 --port 9100 &

# Keep container alive
wait

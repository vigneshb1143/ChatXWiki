FROM python:3.12-slim

WORKDIR /app

# system deps (weaviate-client and langchain are pure-python, but install git/build tools)
RUN apt-get update && \
    apt-get install -y build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# Run FastMCP HTTP transport
CMD ["bash", "services.sh"]
# CMD ["tail", "-f", "/dev/null"]
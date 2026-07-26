# InstaGPT GraphRAG

A URL-to-Knowledge-Graph pipeline that transcribes web content, enriches it with web search, categorizes entities, and stores them in a neural graph database.

## Overview

InstaGPT GraphRAG transforms web URLs into structured knowledge graphs. It extracts content from web pages, enriches it with contextual web searches, identifies and categorizes entities, and stores everything in a graph database for retrieval-augmented generation (RAG) workflows.

## Architecture

```
URL → Extract → Chunk → Embed → Enrich → Categorize → Graph Store
                          ↓
                    Vector DB (Qdrant)
```

### Core Modules

| Module | Description |
|--------|-------------|
| `src/extraction` | Web scraping and content extraction using Trafilatura, BeautifulSoup, and Playwright |
| `src/vector` | Embedding generation (OpenAI/sentence-transformers) and Qdrant vector storage |
| `src/enrichment` | Entity detection via LLM, web search enrichment, and categorization |
| `src/graph` | Neo4j graph database operations and knowledge graph management |
| `src/pipeline` | Orchestration of all stages into a unified pipeline |
| `src/config` | Pydantic-based settings and data models |
| `src/output` | Markdown and JSON output generation |

### Pipeline Stages

1. **Extract** - Fetch and parse web content into clean text
2. **Chunk** - Split text into semantic chunks with overlap
3. **Embed** - Generate vector embeddings for each chunk
4. **Store Chunks** - Upsert embeddings into Qdrant
5. **Enrich** - Detect entities and enrich with web search context
6. **Categorize** - Assign topics and sub-topics to entities
7. **Output** - Generate Markdown and JSON reports
8. **Graph Update** - Merge entities and relationships into Neo4j

## Tech Stack

### Backend
- **Python 3.11+** - Core language
- **FastAPI** - API server and WebSocket support
- **Neo4j** - Graph database for knowledge storage
- **Qdrant** - Vector database for embeddings
- **OpenAI / Sentence-Transformers** - Embedding and LLM providers
- **Playwright** - Browser-based web scraping
- **Typer + Rich** - CLI interface
- **Docker Compose** - Multi-service deployment

### Frontend
- **React 19** - UI framework
- **TypeScript** - Type-safe JavaScript
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first styling
- **React Flow** - Interactive graph visualization
- **TanStack Query** - Server state management
- **Zustand** - Client state management
- **React Router** - Client-side routing

## Project Structure

```
instagpt-graphrag/
├── cli.py                  # CLI entry point
├── src/                    # Python backend
│   ├── config/             # Settings and data models
│   ├── extraction/         # Content extraction
│   ├── vector/             # Embeddings and vector DB
│   ├── enrichment/         # Entity enrichment and categorization
│   ├── graph/              # Neo4j graph operations
│   ├── pipeline/           # Pipeline orchestration
│   └── output/             # Output generation
├── frontend/               # React web UI
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Route pages
│   │   ├── services/       # API client functions
│   │   ├── store/          # Zustand state stores
│   │   └── types/          # TypeScript type definitions
│   ├── package.json
│   └── vite.config.ts
├── scripts/                # Utility scripts
├── docs/                   # Documentation
├── docker-compose.yml      # Service orchestration
└── pyproject.toml          # Project configuration
```

## Getting Started

See [HOW_TO_CONTRIBUTE.md](HOW_TO_CONTRIBUTE.md) for setup instructions.

## Configuration

Copy `.env.example` to `.env` and configure your API keys:

```bash
cp .env.example .env
```

Key settings:
- `LLM_PROVIDER` - Primary LLM provider (google, openai, openrouter, nvidia)
- `QDRANT_URL` - Qdrant vector DB endpoint
- `NEO4J_URI` - Neo4j database URI
- `MAX_CHUNK_SIZE` - Text chunk size for embedding

## CLI Usage

```bash
# Process a single URL
python cli.py process https://example.com

# Process multiple URLs concurrently
python cli.py process https://url1.com https://url2.com --concurrent 5

# View knowledge graph stats
python cli.py graph --stats

# Export graph
python cli.py graph --export graphml

# Search the knowledge graph
python cli.py search "machine learning"

# View entity details
python cli.py entity "Python"
```

## Frontend (Web UI)

The project includes a React-based web interface for visualizing and interacting with the knowledge graph.

### Features

- **Home** - Process URLs and view processing status
- **Graph** - Interactive knowledge graph visualization with React Flow
- **Search** - Semantic search across the knowledge base
- **Notebook** - Explore entities and their relationships

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (runs on http://localhost:3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The dev server proxies `/api` requests to the FastAPI backend at `http://localhost:8000`.

### Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Home page - URL processing input |
| `/graph` | Interactive graph visualization |
| `/search` | Semantic search interface |
| `/notebook` | Entity exploration and details |

## License

MIT

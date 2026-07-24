# How to Contribute

A step-by-step guide for first-time contributors.

## Quick Start

```bash
# 1. Fork on GitHub (click Fork button)

# 2. Clone your fork
git clone https://github.com/your-username/instagpt-graphrag.git
cd instagpt-graphrag

# 3. Set up Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Set up frontend (optional)
cd frontend && npm install && cd ..

# 5. Create a branch
git checkout -b feat/my-feature

# 6. Make changes and test
ruff check .
pytest

# 7. Commit and push
git add .
git commit -m "feat: add my feature"
git push origin feat/my-feature

# 8. Open a PR on GitHub
```

## Step-by-Step Guide

### Step 1: Fork the Repository

1. Go to https://github.com/Hayato-ultra/instagpt-graphrag
2. Click the **Fork** button (top right)
3. Select your GitHub account

### Step 2: Clone Your Fork

```bash
git clone https://github.com/your-username/instagpt-graphrag.git
cd instagpt-graphrag
```

### Step 3: Set Up Development Environment

#### Backend (Python)

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Copy environment file
cp .env.example .env
```

#### Frontend (React/TypeScript)

```bash
cd frontend

# Install Node.js dependencies
npm install

# Return to project root
cd ..
```

**Requirements:** Node.js 18+ and npm 9+

### Step 4: Configure API Keys

Edit `.env` and add your API keys:

```
OPENAI_API_KEY=sk-your-key-here
GOOGLE_API_KEY=your-google-key-here
```

At minimum, you need one LLM provider configured to run the enrichment pipeline.

### Step 5: Start Required Services

```bash
# Start Qdrant (vector DB)
docker-compose up -d qdrant

# Start Neo4j (graph DB)
docker-compose up -d neo4j
```

Or use cloud-hosted instances and update `.env` accordingly.

### Step 6: Create a Feature Branch

```bash
# Ensure you're on main
git checkout main
git pull origin main

# Create and switch to feature branch
git checkout -b feat/your-feature-name
```

Branch naming conventions:
- `feat/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `test/` - Test additions
- `refactor/` - Code refactoring

### Step 7: Make Your Changes

1. Edit files in the `src/` directory
2. Follow the [coding standards](CONTRIBUTING.md#coding-standards)
3. Add tests for new functionality

### Step 8: Run Quality Checks

#### Backend

```bash
# Lint
ruff check .

# Format
ruff format .

# Type check
mypy src/

# Tests
pytest
```

#### Frontend

```bash
cd frontend

# Type check
npx tsc --noEmit

# Lint
npm run lint

# Build (catches compile errors)
npm run build

cd ..
```

### Step 9: Commit Your Changes

```bash
# Stage files
git add src/your-changed-file.py

# Commit with conventional message
git commit -m "feat(module): add new functionality"

# Push to your fork
git push origin feat/your-feature-name
```

### Step 10: Open a Pull Request

1. Go to your fork on GitHub
2. Click **Compare & pull request**
3. Fill in the PR description
4. Select `main` as the base branch
5. Click **Create pull request**

## Finding Things to Work On

### Good First Issues

Look for issues labeled:
- `good first issue` - Beginner-friendly tasks
- `help wanted` - Prioritized community contributions
- `documentation` - Doc improvements

### Contribution Ideas

#### Backend
- Add a new extraction method (e.g., PDF support)
- Improve entity categorization accuracy
- Add tests for existing modules
- Improve error handling and logging
- Add CLI options for pipeline configuration

#### Frontend
- Add new graph visualization features
- Improve search UI with filters
- Add entity detail pages
- Create dark mode toggle
- Add loading states and error handling
- Improve mobile responsiveness

## Common Tasks

### Adding a New Pipeline Stage

1. Create module in `src/`
2. Add stage to `PipelineStage` in `src/config/models.py`
3. Integrate in `src/pipeline/pipeline.py`
4. Add tests

### Adding a New LLM Provider

1. Add provider class in `src/enrichment/llm_client.py`
2. Add provider option in `src/config/config.py`
3. Update documentation

### Improving Extraction

1. Modify `src/extraction/extractor.py`
2. Add handling for new content types
3. Test with various URL formats

### Adding a Frontend Page

1. Create page component in `frontend/src/pages/`
2. Add route in `frontend/src/App.tsx`
3. Add navigation link in `Layout.tsx`
4. Create API service in `frontend/src/services/`

### Modifying Graph Visualization

1. Edit components in `frontend/src/components/`
2. Uses React Flow (`@xyflow/react`)
3. Check `frontend/src/types/` for node/edge types

## Getting Help

- Open an issue with the `question` label
- Review existing code for patterns
- Check the README and docs directory

## Thank You!

Every contribution helps improve InstaGPT GraphRAG. Whether it's fixing a typo, adding a feature, or improving documentation, your work is valued.

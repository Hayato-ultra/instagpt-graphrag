# Contributing to InstaGPT GraphRAG

Thank you for your interest in contributing! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help create a welcoming environment for all contributors

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment (see below)
4. Create a feature branch
5. Make your changes
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Git
- Docker (optional, for services)

### Local Setup

```bash
# Clone your fork
git clone https://github.com/your-username/instagpt-graphrag.git
cd instagpt-graphrag

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Copy environment file
cp .env.example .env
# Edit .env with your API keys
```

### Running Services

```bash
# Start Qdrant and Neo4j
docker-compose up -d qdrant neo4j
```

## How to Contribute

### Types of Contributions

- **Bug fixes** - Fix issues in existing functionality
- **Features** - Add new capabilities to the pipeline
- **Documentation** - Improve docs, add examples, fix typos
- **Tests** - Add or improve test coverage
- **Refactoring** - Improve code quality without changing behavior

### Finding Issues

- Check the issue tracker for open issues
- Look for issues labeled `good first issue` for beginners
- Issues labeled `help wanted` are prioritized for community contributions

## Coding Standards

### Python (Backend)

#### Style

This project uses **Ruff** for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

#### Type Hints

All functions must have complete type hints:

```python
def process_url(url: str, timeout: int = 30) -> ProcessingResult:
    """Process a URL and return results."""
    ...
```

#### Docstrings

Use Google-style docstrings for public functions:

```python
async def extract(self, url: str) -> ExtractedContent:
    """Extract content from a URL.

    Args:
        url: The URL to extract content from.

    Returns:
        ExtractedContent with title, text, and metadata.

    Raises:
        ExtractionError: If content cannot be extracted.
    """
```

### TypeScript/React (Frontend)

#### Style

- Use TypeScript for all files (`.tsx` for components, `.ts` for utilities)
- Use functional components with hooks
- Follow React best practices

#### Type Safety

```typescript
interface ProcessUrlProps {
  url: string;
  onResult: (result: ProcessingResult) => void;
  onError?: (error: Error) => void;
}

export function ProcessUrl({ url, onResult, onError }: ProcessUrlProps) {
  // ...
}
```

#### State Management

- Use Zustand for global state
- Use TanStack Query for server state
- Keep local state in components when appropriate

### Testing

Write tests for new functionality:

```bash
# Python tests
pytest

# Run with coverage
pytest --cov=src

# Frontend tests (when configured)
cd frontend && npm test
```

## Commit Messages

Follow conventional commit format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Code style changes (formatting, no logic change) |
| `refactor` | Code refactoring |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks |

### Examples

```
feat(extraction): add support for PDF parsing

fix(vector): handle empty embedding vectors

docs: update installation instructions

test(enrichment): add unit tests for categorizer
```

## Pull Request Process

1. **Create a feature branch** from `main`
2. **Make your changes** following the coding standards
3. **Write or update tests** for your changes
4. **Run the linter and tests**:

   Backend:
   ```bash
   ruff check .
   ruff format .
   pytest
   ```

   Frontend (if applicable):
   ```bash
   cd frontend
   npx tsc --noEmit
   npm run build
   cd ..
   ```

5. **Update documentation** if needed
6. **Submit your PR** with a clear description

### PR Description Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Other

## Testing
Describe tests you ran and results.

## Checklist
- [ ] Code follows project style
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] No new warnings
```

## Reporting Issues

### Bug Reports

Include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Python version and OS
- Relevant logs

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternatives considered

## Questions?

Open an issue with the `question` label or start a discussion in the repository.

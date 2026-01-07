# Chatbot POC

A proof of concept chatbot application built with LangChain and OpenAI.

## Description

This project provides a simple chatbot proof of concept using LangChain and OpenAI's models.

### Graph architecture

![Graph](graph.webp)

## Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key (set in `.env` file)

## Installation

1. Clone the repository

   ```bash
   git clone <repository-url>
   cd ai_chatbot
   ```

2. Set up environment variables

   ```bash
   cp .env.example .env
   ```

   Then edit the `.env` file to add your OpenAI API key.

3. Install dependencies
   ```bash
   uv sync --dev
   ```

## Development Setup

After installing dependencies, set up the development environment:

1. **Install pre-commit hooks**

   ```bash
   uv run pre-commit install
   ```

   This installs git hooks that automatically run linting and formatting on each commit.

2. **Verify the setup** (optional)
   ```bash
   uv run pre-commit run --all-files
   ```
   This runs all hooks on all files to ensure everything is properly configured.

### Pre-commit Hooks

The project uses the following pre-commit hooks:

| Hook                      | Description                                 |
| ------------------------- | ------------------------------------------- |
| `trailing-whitespace`     | Removes trailing whitespace from lines      |
| `end-of-file-fixer`       | Ensures files end with a single newline     |
| `check-yaml`              | Validates YAML file syntax                  |
| `check-added-large-files` | Prevents committing files larger than 500KB |
| `check-merge-conflict`    | Detects unresolved merge conflict markers   |
| `ruff-check`              | Runs Ruff linter with auto-fix              |
| `ruff-format`             | Runs Ruff code formatter                    |

### Manual Linting

You can also run linting and formatting manually:

```bash
uv run ruff check .        # Run linting
uv run ruff check . --fix  # Run linting with auto-fix
uv run ruff format .       # Run formatting
```

## Usage

### Terminal Interface

Run the application in the terminal:

```bash
uv run -m src.main
```

### Streamlit UI

The application also provides a web-based UI using Streamlit:

```bash
uv run -m src.main --ui
```

This will launch a Streamlit server and open a browser window with the chatbot interface. If the browser doesn't open automatically, go to http://localhost:8501.

---

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/manelcardenas/chatbot_poc)

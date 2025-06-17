# Chatbot POC

A proof of concept chatbot application built with LangChain and OpenAI.

## Description

This project provides a simple chatbot proof of concept using LangChain and OpenAI's models.

### Graph architecture

![Graph](graph.webp)

## Prerequisites

- Python 3.11 or higher
- OpenAI API key (set in `.env` file)

## Installation

1. Clone the repository
   ```
   git clone <repository-url>
   cd chatbot-poc
   ```

2. Set up environment variables
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file to add your OpenAI API key.

3. Install dependencies using one of these methods:

   **Option 1: Using setup script (Unix/macOS)**
   ```
   ./setup.sh
   ```
   This script creates a virtual environment, activates it, and installs dependencies.

   **Option 2: Manual installation**
   ```
   # Create and activate virtual environment
   python -m venv .venv
   source .venv/bin/activate
   
   # Or using pip
   pip install -e .
   ```

## Usage

### Terminal Interface

Run the application in the terminal:

```
uv run -m src.main
```
or
```
python -m src.main
```

### Streamlit UI

The application also provides a web-based UI using Streamlit:

```
uv run -m src.main --ui
```
or
```
python -m src.main --ui
```

This will launch a Streamlit server and open a browser window with the chatbot interface. If the browser doesn't open automatically, go to http://localhost:8501.

## Development

### Linting

The project uses Ruff for linting and formatting:

```
ruff check .   # Run linting
ruff format .  # Run formatting
```



[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/manelcardenas/chatbot_poc)

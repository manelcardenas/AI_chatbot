# Chat LangChain - Architecture Overview

> Reference implementation analysis of [chat-langchain](https://github.com/langchain-ai/chat-langchain), LangChain's official documentation chatbot.

## Table of Contents

- [System Overview](#system-overview)
- [High-Level Architecture](#high-level-architecture)
- [Graph Structure](#graph-structure)
  - [Parent Graph: RetrievalGraph](#parent-graph-retrievalgraph)
  - [Child Graph: ResearcherGraph](#child-graph-researchergraph)
- [Data Flow](#data-flow)
- [File Structure](#file-structure)

---

## System Overview

The chat-langchain system consists of two main pipelines:

| Pipeline | When | Purpose |
|----------|------|---------|
| **Ingestion** | Offline (scheduled) | Crawl docs, parse, chunk, embed, store in vector DB |
| **Retrieval** | Runtime (per query) | Plan research, retrieve docs, generate answer |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM ARCHITECTURE                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INGESTION PIPELINE (Offline)                      │   │
│  │                                                                      │   │
│  │   Documentation Sites                                                │   │
│  │   (python.langchain.com, js.langchain.com, docs.langchain.com)      │   │
│  │          │                                                           │   │
│  │          ▼                                                           │   │
│  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │   │
│  │   │  SitemapLoader│───►│  HTML Parser │───►│ Text Splitter│          │   │
│  │   │  (crawl)     │    │  (→ Markdown)│    │ (chunking)   │          │   │
│  │   └──────────────┘    └──────────────┘    └──────────────┘          │   │
│  │                                                  │                   │   │
│  │                                                  ▼                   │   │
│  │                              ┌──────────────────────────────┐       │   │
│  │                              │   OpenAI Embeddings API      │       │   │
│  │                              │   (text → vectors)           │       │   │
│  │                              └──────────────────────────────┘       │   │
│  │                                                  │                   │   │
│  │                                                  ▼                   │   │
│  │                              ┌──────────────────────────────┐       │   │
│  │                              │   WEAVIATE (Vector Database) │       │   │
│  │                              │   - text chunks              │       │   │
│  │                              │   - embedding vectors        │       │   │
│  │                              │   - metadata                 │       │   │
│  │                              └──────────────────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                         │                                   │
│                                         │ Vector similarity search          │
│                                         ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RETRIEVAL PIPELINE (Runtime)                      │   │
│  │                                                                      │   │
│  │   User Query                                                         │   │
│  │       │                                                              │   │
│  │       ▼                                                              │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │              RetrievalGraph (Parent)                         │   │   │
│  │   │                                                              │   │   │
│  │   │   create_research_plan ──► conduct_research ──► respond      │   │   │
│  │   │                                   │                          │   │   │
│  │   │                                   ▼                          │   │   │
│  │   │                        ┌───────────────────┐                 │   │   │
│  │   │                        │ ResearcherGraph   │                 │   │   │
│  │   │                        │ (Child)           │                 │   │   │
│  │   │                        └───────────────────┘                 │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  │       │                                                              │   │
│  │       ▼                                                              │   │
│  │   Final Answer                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## High-Level Architecture

The retrieval system uses a **hierarchical graph pattern** (nested graphs) with LangGraph:

- **Parent Graph** (`RetrievalGraph`): Orchestrates the overall flow - planning, looping through research steps, generating final response
- **Child Graph** (`ResearcherGraph`): Handles individual research steps - query expansion and parallel document retrieval

This separation provides:
- **Modularity**: Each graph can be tested/modified independently
- **Reusability**: The researcher graph could be used in other contexts
- **Clarity**: Clear separation between "what to research" and "how to retrieve"

---

## Graph Structure

### Parent Graph: RetrievalGraph

**Source:** `backend/retrieval_graph/graph.py`

```
┌─────────────────────────────────────────────────────────────────────┐
│                       RetrievalGraph                                 │
│                                                                     │
│   START                                                             │
│     │                                                               │
│     ▼                                                               │
│   ┌─────────────────────┐                                           │
│   │ create_research_plan│  Generate list of research steps          │
│   └─────────────────────┘                                           │
│     │                                                               │
│     ▼                                                               │
│   ┌─────────────────────┐     ┌───────────────────────────────────┐ │
│   │  conduct_research   │────►│  ResearcherGraph (subgraph)       │ │
│   └─────────────────────┘     └───────────────────────────────────┘ │
│     │                                                               │
│     ▼                                                               │
│   ┌─────────────────────┐                                           │
│   │   check_finished    │  Conditional: more steps?                 │
│   └─────────────────────┘                                           │
│     │              │                                                │
│     │(steps==0)    │(steps>0)                                       │
│     ▼              └──────────────────────┐                         │
│   ┌─────────────────────┐                 │                         │
│   │       respond       │  Generate final │                         │
│   └─────────────────────┘  answer         │                         │
│     │                                     │                         │
│     ▼                                     │                         │
│    END ◄──────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘
```

#### Nodes

| Node | Input | Output | Purpose |
|------|-------|--------|---------|
| `create_research_plan` | User query + chat history | List of research steps | LLM generates a plan to answer the question |
| `conduct_research` | First step from plan | Retrieved documents | Invokes ResearcherGraph, removes completed step |
| `check_finished` | Remaining steps | Route decision | If steps remain → loop; else → respond |
| `respond` | All documents + history | Final answer | LLM synthesizes answer from retrieved context |

#### State Schema

```python
@dataclass
class AgentState:
    messages: list[AnyMessage]        # Conversation history
    steps: list[str]                  # Research plan (consumed iteratively)
    documents: list[Document]         # Accumulated retrieved documents
    answer: str                       # Final response
    query: str                        # Original user query
```

---

### Child Graph: ResearcherGraph

**Source:** `backend/retrieval_graph/researcher_graph/graph.py`

```
┌─────────────────────────────────────────────────────────────────────┐
│                       ResearcherGraph                                │
│                                                                     │
│   START                                                             │
│     │                                                               │
│     ▼                                                               │
│   ┌─────────────────────┐                                           │
│   │  generate_queries   │  LLM expands step into multiple queries   │
│   └─────────────────────┘                                           │
│     │                                                               │
│     ▼                                                               │
│   ┌─────────────────────┐                                           │
│   │retrieve_in_parallel │  Fan-out using Send()                     │
│   └─────────────────────┘                                           │
│     │         │         │                                           │
│     ▼         ▼         ▼                                           │
│   ┌─────┐   ┌─────┐   ┌─────┐                                       │
│   │ ret │   │ ret │   │ ret │   Parallel vector store queries       │
│   └─────┘   └─────┘   └─────┘                                       │
│     │         │         │                                           │
│     └────┬────┴────┬────┘                                           │
│          │         │                                                │
│          ▼         ▼                                                │
│   ┌─────────────────────┐                                           │
│   │   reduce_docs       │  Merge & deduplicate results              │
│   └─────────────────────┘                                           │
│     │                                                               │
│     ▼                                                               │
│    END ──► Returns documents to parent graph                        │
└─────────────────────────────────────────────────────────────────────┘
```

#### Nodes

| Node | Input | Output | Purpose |
|------|-------|--------|---------|
| `generate_queries` | Research step (question) | List of search queries | Query expansion for better recall |
| `retrieve_in_parallel` | List of queries | Send commands | Dispatches parallel retrieval tasks |
| `retrieve_documents` | Single query | Documents | Vector similarity search in Weaviate |

#### State Schema

```python
@dataclass
class ResearcherState:
    question: str                     # A single research step from parent
    queries: list[str]                # Expanded search queries
    documents: list[Document]         # Retrieved documents (merged from parallel)
    query_index: int                  # Tracks which query produced results
```

---

## Data Flow

### Example: User asks "How do I use LCEL with streaming?"

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: create_research_plan                                                 │
│                                                                             │
│ Input:  "How do I use LCEL with streaming?"                                 │
│ Output: steps = ["LCEL basics and syntax",                                  │
│                  "Streaming in LangChain",                                  │
│                  "LCEL streaming examples"]                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: conduct_research (step: "LCEL basics and syntax")                    │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ ResearcherGraph                                                          │ │
│ │                                                                          │ │
│ │ generate_queries:                                                        │ │
│ │   → ["LCEL LangChain", "LangChain Expression Language", "LCEL syntax"]  │ │
│ │                                                                          │ │
│ │ retrieve_documents (×3 parallel):                                        │ │
│ │   → [doc1, doc2, doc3, doc4, doc5, ...]                                 │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ state.documents = [doc1, doc2, doc3, doc4, doc5]                           │
│ state.steps = ["Streaming in LangChain", "LCEL streaming examples"]        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: check_finished                                                       │
│                                                                             │
│ steps.length = 2 → Route to: conduct_research                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4-5: conduct_research × 2 more iterations                               │
│                                                                             │
│ ... accumulates more documents into state.documents ...                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: check_finished                                                       │
│                                                                             │
│ steps.length = 0 → Route to: respond                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: respond                                                              │
│                                                                             │
│ Input:  state.documents (all accumulated), state.messages                   │
│ Output: Final comprehensive answer with citations                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
backend/
├── configuration.py          # Base config (embeddings, retriever, search params)
├── constants.py              # Weaviate index names
├── embeddings.py             # Embeddings model factory
├── ingest.py                 # Document ingestion pipeline
├── parser.py                 # HTML → Markdown converter
├── retrieval.py              # Retriever factory (Weaviate connection)
├── utils.py                  # Shared utilities
│
├── retrieval_graph/          # Main retrieval system
│   ├── __init__.py
│   ├── graph.py              # Parent graph (RetrievalGraph)
│   ├── state.py              # Parent state definitions
│   ├── configuration.py      # Agent-specific config
│   ├── prompts.py            # System prompts (pulled from LangSmith)
│   │
│   └── researcher_graph/     # Subgraph for document retrieval
│       ├── __init__.py
│       ├── graph.py          # Child graph (ResearcherGraph)
│       └── state.py          # Child state definitions
│
└── tests/
    └── evals/
        └── test_e2e.py       # LangSmith evaluation suite
```

---

## Next Steps

For detailed implementation patterns, code explanations, and best practices, see:
- **[Implementation Guide](./implementation-guide.md)** - Deep dive into each component

---

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Chat LangChain Repository](https://github.com/langchain-ai/chat-langchain)
- [LangGraph Subgraphs](https://langchain-ai.github.io/langgraph/how-tos/subgraph/)
- [LangGraph Send API](https://langchain-ai.github.io/langgraph/how-tos/send/)

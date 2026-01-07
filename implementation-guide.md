# Chat LangChain - Implementation Guide

> Deep dive into the implementation patterns, code logic, and best practices used in [chat-langchain](https://github.com/langchain-ai/chat-langchain).

## Table of Contents

- [1. Configuration System](#1-configuration-system)
- [2. Ingestion Pipeline](#2-ingestion-pipeline)
- [3. Document Parsing](#3-document-parsing)
- [4. Vector Store & Retrieval](#4-vector-store--retrieval)
- [5. State Management & Reducers](#5-state-management--reducers)
- [6. Utility Functions](#6-utility-functions)
- [7. Prompts](#7-prompts)
- [8. Evaluation & Testing](#8-evaluation--testing)
- [9. Key Patterns & Best Practices](#9-key-patterns--best-practices)

---

## 1. Configuration System

**Files:** `backend/configuration.py`, `backend/retrieval_graph/configuration.py`

### Purpose

The configuration system provides **runtime-configurable parameters** that can be overridden when invoking the graph.

### Base Configuration

```python
@dataclass(kw_only=True)
class BaseConfiguration:
    embedding_model: str = "openai/text-embedding-3-small"
    retriever_provider: Literal["weaviate"] = "weaviate"
    search_kwargs: dict[str, Any] = field(default_factory=dict)
    k: int = 6  # Deprecated, use search_kwargs
```

### Agent Configuration (extends Base)

```python
@dataclass(kw_only=True)
class AgentConfiguration(BaseConfiguration):
    query_model: str = "anthropic/claude-3-5-haiku-20241022"
    response_model: str = "anthropic/claude-3-5-haiku-20241022"

    # Prompts (pulled from LangSmith at import time)
    router_system_prompt: str = field(default=prompts.ROUTER_SYSTEM_PROMPT)
    research_plan_system_prompt: str = field(default=prompts.RESEARCH_PLAN_SYSTEM_PROMPT)
    # ... more prompts
```

### Runtime Configuration Pattern

The key method `from_runnable_config` extracts config from LangGraph's `RunnableConfig`:

```python
@classmethod
def from_runnable_config(cls, config: RunnableConfig) -> T:
    config = ensure_config(config)
    configurable = config.get("configurable") or {}
    # Extract only fields that exist in this dataclass
    _fields = {f.name for f in fields(cls) if f.init}
    return cls(**{k: v for k, v in configurable.items() if k in _fields})
```

### Usage in Nodes

```python
async def respond(state: AgentState, *, config: RunnableConfig):
    # Extract configuration
    configuration = AgentConfiguration.from_runnable_config(config)

    # Use configured model
    model = load_chat_model(configuration.response_model)
```

### Client-Side Override

Users can customize behavior at runtime:

```python
result = await graph.ainvoke(
    {"messages": [("human", "What is LCEL?")]},
    config={
        "configurable": {
            "response_model": "openai/gpt-4o",
            "k": 10,  # Retrieve more documents
        }
    }
)
```

### Backwards Compatibility

The system handles old API parameters gracefully:

```python
def _update_configurable_for_backwards_compatibility(configurable: dict) -> dict:
    if "k" in configurable:
        update["search_kwargs"] = {"k": configurable["k"]}
    if "model_name" in configurable:
        update["response_model"] = MODEL_NAME_TO_RESPONSE_MODEL.get(
            configurable["model_name"], configurable["model_name"]
        )
    return {**configurable, **update}
```

---

## 2. Ingestion Pipeline

**File:** `backend/ingest.py`

### Overview

The ingestion pipeline crawls documentation websites, processes the HTML, and stores embeddings in Weaviate.

```
Documentation Sites → SitemapLoader → Parser → Splitter → Embeddings → Weaviate
```

### Data Sources

```python
def ingest_general_guides_and_tutorials():
    langchain_python_docs = load_langchain_python_docs()  # python.langchain.com
    langchain_js_docs = load_langchain_js_docs()          # js.langchain.com
    aggregated_site_docs = load_aggregated_docs_site()    # docs.langchain.com
    return langchain_python_docs + langchain_js_docs + aggregated_site_docs
```

### Loading with SitemapLoader

```python
def load_langchain_python_docs():
    return SitemapLoader(
        "https://python.langchain.com/sitemap.xml",
        filter_urls=["https://python.langchain.com/"],
        parsing_function=langchain_docs_extractor,  # Custom HTML parser
        default_parser="lxml",
        bs_kwargs={
            "parse_only": SoupStrainer(
                name=("article", "title", "html", "lang", "content")
            ),
        },
        meta_function=metadata_extractor,  # Extract title, description, etc.
    ).load()
```

### Metadata Extraction

```python
def metadata_extractor(meta: dict, soup: BeautifulSoup, title_suffix: str = None) -> dict:
    title_element = soup.find("title")
    description_element = soup.find("meta", attrs={"name": "description"})

    return {
        "source": meta["loc"],        # URL
        "title": title_element.get_text() if title_element else "",
        "description": description_element.get("content", "") if description_element else "",
        "language": soup.find("html").get("lang", ""),
        **meta,
    }
```

### Chunking

```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=4000,    # Characters per chunk
    chunk_overlap=200   # Overlap to preserve context
)
docs_transformed = text_splitter.split_documents(documents)

# Filter out tiny chunks
docs_transformed = [doc for doc in docs_transformed if len(doc.page_content) > 10]
```

### Indexing with Deduplication

```python
# SQLRecordManager tracks what's been indexed
record_manager = SQLRecordManager(
    f"weaviate/{INDEX_NAME}",
    db_url=RECORD_MANAGER_DB_URL,
)
record_manager.create_schema()

# Index with cleanup of stale documents
indexing_stats = index(
    docs_transformed,
    record_manager,
    vectorstore,
    cleanup="full",           # Remove docs that no longer exist
    source_id_key="source",   # Use URL as unique identifier
    force_update=False,       # Set True to re-index everything
)
```

### Why SQLRecordManager?

Without it, re-running ingestion would create duplicates. The record manager:
- Tracks which documents are already indexed (by source URL)
- Detects when documents have changed (content hash)
- Removes documents that no longer exist in the source (`cleanup="full"`)

---

## 3. Document Parsing

**File:** `backend/parser.py`

### Purpose

Converts raw HTML from documentation sites into clean Markdown, preserving semantic structure while removing noise.

### Why Markdown?

| HTML | Markdown |
|------|----------|
| `<h1>Title</h1>` | `# Title` |
| `<a href="url">text</a>` | `[text](url)` |
| `<pre><code class="language-python">...</code></pre>` | ` ```python\n...\n``` ` |
| `<div class="nav">...</div>` | (removed - not useful) |

**Benefits:**
- Fewer tokens (cheaper, faster)
- Cleaner context for LLM
- Preserves structure (headers, lists, code blocks)
- Removes navigation, styling, scripts

### Implementation Highlights

```python
def langchain_docs_extractor(soup: BeautifulSoup) -> str:
    # Remove non-content elements
    SCAPE_TAGS = ["nav", "footer", "aside", "script", "style"]
    [tag.decompose() for tag in soup.find_all(SCAPE_TAGS)]

    def get_text(tag: Tag) -> Generator[str, None, None]:
        for child in tag.children:
            if isinstance(child, NavigableString):
                yield child
            elif isinstance(child, Tag):
                # Convert HTML elements to Markdown
                if child.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    yield f"{'#' * int(child.name[1:])} {child.get_text()}\n\n"
                elif child.name == "a":
                    yield f"[{child.get_text()}]({child.get('href')})"
                elif child.name == "code":
                    # Handle code blocks with language detection
                    if parent.name == "pre":
                        language = extract_language(parent)
                        yield f"```{language}\n{code_content}\n```\n\n"
                    else:
                        yield f"`{child.get_text()}`"
                # ... more conversions
```

### Special Handling: Tabbed Content

LangChain docs use tabs (e.g., Python vs JavaScript examples):

```python
elif child.name == "div" and "tabs-container" in child.attrs.get("class", [""]):
    tabs = child.find_all("li", {"role": "tab"})
    tab_panels = child.find_all("div", {"role": "tabpanel"})
    for tab, tab_panel in zip(tabs, tab_panels):
        tab_name = tab.get_text(strip=True)
        yield f"{tab_name}\n"
        yield from get_text(tab_panel)
```

---

## 4. Vector Store & Retrieval

**Files:** `backend/retrieval.py`, `backend/constants.py`, `backend/embeddings.py`

### Weaviate as the Vector Database

Weaviate stores:
- **Text content**: The actual document chunks
- **Embedding vectors**: Numerical representations for similarity search
- **Metadata**: Source URL, title (for citations)

### Index Naming Convention

```python
# constants.py
WEAVIATE_GENERAL_GUIDES_AND_TUTORIALS_INDEX_NAME = (
    "LangChain_General_Guides_And_Tutorials_OpenAI_text_embedding_3_small"
)
```

**Why include embedding model in name?** Different embedding models produce incompatible vectors. This prevents accidentally mixing them.

### Retriever Factory

```python
@contextmanager
def make_retriever(config: RunnableConfig) -> Iterator[BaseRetriever]:
    """Create a retriever based on configuration."""
    configuration = BaseConfiguration.from_runnable_config(config)
    embedding_model = make_text_encoder(configuration.embedding_model)

    match configuration.retriever_provider:
        case "weaviate":
            with make_weaviate_retriever(configuration, embedding_model) as retriever:
                yield retriever
        case _:
            raise ValueError(f"Unknown provider: {configuration.retriever_provider}")
```

### Weaviate Connection Management

```python
@contextmanager
def make_weaviate_retriever(config, embedding_model) -> Iterator[BaseRetriever]:
    # Context manager ensures proper connection cleanup
    with weaviate.connect_to_weaviate_cloud(
        cluster_url=os.environ["WEAVIATE_URL"],
        auth_credentials=weaviate.classes.init.Auth.api_key(
            os.environ["WEAVIATE_API_KEY"]
        ),
        skip_init_checks=True,
    ) as weaviate_client:
        store = WeaviateVectorStore(
            client=weaviate_client,
            index_name=INDEX_NAME,
            text_key="text",
            embedding=embedding_model,
            attributes=["source", "title"],  # Metadata to return
        )
        search_kwargs = {**config.search_kwargs, "return_uuids": True}
        yield store.as_retriever(search_kwargs=search_kwargs)
```

### Embedding Model Factory

```python
def make_text_encoder(model: str) -> Embeddings:
    """Support provider/model format."""
    provider, model_name = model.split("/", maxsplit=1)
    match provider:
        case "openai":
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(model=model_name)
        case _:
            raise ValueError(f"Unsupported provider: {provider}")
```

### Usage in Graph

```python
async def retrieve_documents(state: QueryState, *, config: RunnableConfig):
    with retrieval.make_retriever(config) as retriever:
        response = await retriever.ainvoke(state.query, config)
    return {"documents": response, "query_index": state.query_index}
```

---

## 5. State Management & Reducers

**Files:** `backend/retrieval_graph/state.py`, `backend/utils.py`

### The Problem: Parallel Updates

When multiple nodes run in parallel (via `Send`), they all try to update the same state field:

```
generate_queries → ["query1", "query2", "query3"]
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    retrieve(q1)   retrieve(q2)   retrieve(q3)
         │             │             │
         ▼             ▼             ▼
    [doc1, doc2]   [doc3, doc4]   [doc1, doc5]  ← doc1 is duplicate!
         │             │             │
         └─────────────┴─────────────┘
                       │
                       ▼
              How to merge these?
```

### The Solution: State Reducers

LangGraph allows annotating state fields with **reducer functions**:

```python
from typing import Annotated

@dataclass
class ResearcherState:
    documents: Annotated[list[Document], reduce_docs] = field(default_factory=list)
    #                                    ^^^^^^^^^^^
    #                                    Reducer function
```

When parallel nodes update `documents`, LangGraph calls:
```python
state.documents = reduce_docs(existing=current_docs, new=new_docs_from_node)
```

### The `reduce_docs` Function

```python
def reduce_docs(
    existing: Optional[list[Document]],
    new: Union[list[Document], list[dict], list[str], str, Literal["delete"]],
) -> list[Document]:
    """Merge documents with deduplication."""

    # Special case: clear all documents
    if new == "delete":
        return []

    existing_list = list(existing) if existing else []

    # Track existing UUIDs to prevent duplicates
    existing_ids = set(doc.metadata.get("uuid") for doc in existing_list)

    new_list = []
    for item in new:
        if isinstance(item, Document):
            item_id = item.metadata.get("uuid")

            # Assign UUID if missing
            if item_id is None:
                item_id = str(uuid.uuid4())
                item.metadata["uuid"] = item_id

            # Only add if not duplicate
            if item_id not in existing_ids:
                new_list.append(item)
                existing_ids.add(item_id)

    return existing_list + new_list
```

### Why UUIDs?

Documents from Weaviate include UUIDs. When the same document matches multiple queries, deduplication prevents it from appearing multiple times in the context.

### The `add_messages` Reducer

For chat messages, LangChain provides a built-in reducer:

```python
from langgraph.graph import add_messages

@dataclass
class AgentState:
    messages: Annotated[list[AnyMessage], add_messages]
```

This handles:
- Appending new messages
- Updating existing messages (by ID)
- Proper message ordering

---

## 6. Utility Functions

**File:** `backend/utils.py`

### `format_docs` - Document Formatting for LLM

Converts documents to XML format for inclusion in prompts:

```python
def format_docs(docs: Optional[list[Document]]) -> str:
    if not docs:
        return "<documents></documents>"

    formatted = "\n".join(_format_doc(doc) for doc in docs)
    return f"<documents>\n{formatted}\n</documents>"

def _format_doc(doc: Document) -> str:
    metadata = doc.metadata or {}
    meta = "".join(f" {k}={v!r}" for k, v in metadata.items())
    return f"<document{meta}>\n{doc.page_content}\n</document>"
```

**Example output:**
```xml
<documents>
<document source='https://python.langchain.com/docs/expression_language/' title='LCEL'>
LangChain Expression Language (LCEL) is a declarative way to compose chains...
</document>
<document source='https://python.langchain.com/docs/expression_language/streaming' title='Streaming'>
LCEL supports streaming out of the box...
</document>
</documents>
```

**Why XML?**
- Clear boundaries between documents
- Metadata preserved inline (for citations)
- LLMs handle XML structure well
- Easy to reference: "According to document with source=..."

### `load_chat_model` - Universal Model Loader

```python
def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Load any chat model using provider/model format."""

    if "/" in fully_specified_name:
        provider, model = fully_specified_name.split("/", maxsplit=1)
    else:
        provider, model = "", fully_specified_name

    model_kwargs = {"temperature": 0, "stream_usage": True}

    # Provider-specific adjustments
    if provider == "google_genai":
        model_kwargs["convert_system_message_to_human"] = True

    return init_chat_model(model, model_provider=provider, **model_kwargs)
```

**Supported formats:**
- `"anthropic/claude-3-5-sonnet-20241022"`
- `"openai/gpt-4o"`
- `"google_genai/gemini-pro"`

---

## 7. Prompts

**File:** `backend/retrieval_graph/prompts.py`

### Current Implementation (LangSmith)

Prompts are pulled from LangSmith Hub at import time:

```python
from langsmith import Client

client = Client()

ROUTER_SYSTEM_PROMPT = (
    client.pull_prompt("langchain-ai/chat-langchain-router-prompt")
    .messages[0].prompt.template
)
```

### Available Prompts

| Prompt | Purpose |
|--------|---------|
| `ROUTER_SYSTEM_PROMPT` | Classify query as `more-info`, `langchain`, or `general` |
| `RESEARCH_PLAN_SYSTEM_PROMPT` | Generate 1-3 step research plan |
| `GENERATE_QUERIES_SYSTEM_PROMPT` | Expand step into multiple search queries |
| `RESPONSE_SYSTEM_PROMPT` | Generate final answer with citations |
| `MORE_INFO_SYSTEM_PROMPT` | Ask user for clarification |
| `GENERAL_SYSTEM_PROMPT` | Politely decline non-LangChain questions |

### Accessing Public Prompts

These prompts are public and can be fetched via API:

```bash
curl -s "https://api.hub.langchain.com/commits/langchain-ai/chat-langchain-response-prompt/latest" \
  | jq -r '.manifest.kwargs.messages[0].kwargs.prompt.kwargs.template'
```

---

## 8. Evaluation & Testing

**File:** `backend/tests/evals/test_e2e.py`

### Evaluation Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| `retrieval_recall` | Did we retrieve at least one correct source? | ≥ 65% |
| `answer_correctness_score` | Is the answer factually correct vs reference? | ≥ 90% |
| `answer_vs_context_correctness_score` | Is answer correct AND supported by context? | ≥ 90% |

### LLM-as-Judge Pattern

Uses Claude 3.5 Haiku to evaluate answers:

```python
class GradeAnswer(BaseModel):
    reason: str = Field(description="1-2 sentences explaining the score")
    score: float = Field(description="0.0 to 1.0", minimum=0.0, maximum=1.0)

QA_SYSTEM_PROMPT = """You are an expert programmer tasked with grading answers...
Grade based ONLY on factual accuracy. Ignore punctuation differences..."""

qa_chain = QA_PROMPT | judge_llm.with_structured_output(GradeAnswer)
```

### Running Evaluations

```python
experiment_results = await aevaluate(
    run_graph,                    # Function to test
    data=DATASET_NAME,            # LangSmith dataset
    evaluators=[                  # Evaluation functions
        evaluate_retrieval_recall,
        evaluate_qa,
        evaluate_qa_context,
    ],
    experiment_prefix="chat-langchain-ci",
    max_concurrency=4,
)
```

---

## 9. Key Patterns & Best Practices

### Pattern 1: Provider/Model String Format

```python
"anthropic/claude-3-5-sonnet-20241022"
"openai/gpt-4o"
"openai/text-embedding-3-small"
```

**Benefits:**
- Single string to configure (easy for users)
- Extensible to new providers
- Clear separation of provider and model

### Pattern 2: Context Managers for Connections

```python
@contextmanager
def make_retriever(config) -> Iterator[BaseRetriever]:
    with weaviate.connect_to_weaviate_cloud(...) as client:
        yield store.as_retriever(...)
    # Connection automatically closed
```

**Benefits:**
- Ensures cleanup even if errors occur
- No leaked connections
- Clear lifecycle management

### Pattern 3: Runtime Configuration Injection

```python
@dataclass
class Configuration:
    model: str = "default"

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig) -> "Configuration":
        configurable = config.get("configurable") or {}
        return cls(**{k: v for k, v in configurable.items() if k in cls_fields})
```

**Benefits:**
- Defaults work out of the box
- Users can override at runtime
- Type-safe configuration

### Pattern 4: State Reducers for Parallel Operations

```python
documents: Annotated[list[Document], reduce_docs]
```

**Benefits:**
- Safe parallel updates
- Automatic deduplication
- Flexible input handling

### Pattern 5: HTML → Markdown Conversion

**Benefits:**
- Cleaner LLM input
- Fewer tokens
- Preserved semantic structure

### Pattern 6: XML-Formatted Context

```xml
<documents>
<document source='url' title='title'>
content
</document>
</documents>
```

**Benefits:**
- Clear document boundaries
- Inline metadata for citations
- LLM-friendly format

---

## Summary

| Component | Key Responsibility |
|-----------|-------------------|
| Configuration | Runtime-overridable parameters |
| Ingestion | Crawl → Parse → Chunk → Embed → Store |
| Parser | HTML → Clean Markdown |
| Retrieval | Vector store abstraction with connection management |
| State Reducers | Safe parallel state updates with deduplication |
| Utils | Document formatting, model loading |
| Prompts | LangSmith-hosted, publicly accessible |
| Evals | LLM-as-judge evaluation suite |

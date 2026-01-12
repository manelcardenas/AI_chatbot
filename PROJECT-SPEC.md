# Project Specification: AI Chatbot

> Technical specification for a RAG-based chatbot deployed on AWS, inspired by [chat-langchain](https://github.com/langchain-ai/chat-langchain).

## Table of Contents

- [Overview](#overview)
- [Architecture Comparison](#architecture-comparison)
- [System Architecture](#system-architecture)
- [Component Details](#component-details)
- [Infrastructure](#infrastructure)
- [Ingestion Pipeline](#ingestion-pipeline)
- [Cost Estimates](#cost-estimates)
- [Security Considerations](#security-considerations)
- [Development Roadmap](#development-roadmap)

---

## Overview

### Project Goals

Build a documentation chatbot that:
- Answers questions about content from a structured website (blog posts)
- Uses RAG (Retrieval Augmented Generation) for accurate, sourced answers
- Streams responses in real-time
- Runs on AWS infrastructure (not LangChain Platform)

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector Database | PostgreSQL + pgvector (RDS) | Single database, ACID compliance, AWS native |
| Compute | ECS Fargate | No cold starts, full streaming, no timeout limits |
| LLM Provider | OpenAI | Hardcoded, no runtime model selection |
| Thread Persistence | None | Stateless per request |
| Frontend | chat-langchain frontend | Reuse existing Next.js app |
| Observability | LangSmith | Tracing and evaluation |

---

## Architecture Comparison

### chat-langchain vs This Project

| Component | chat-langchain | This Project |
|-----------|---------------|--------------|
| **Deployment** | LangGraph Cloud | AWS ECS Fargate |
| **Vector DB** | Weaviate (managed) | PostgreSQL + pgvector (RDS) |
| **Record Manager** | Supabase PostgreSQL | Same RDS instance |
| **Model Selection** | Runtime configurable | Hardcoded (OpenAI) |
| **Thread Storage** | Redis + PostgreSQL | None (stateless) |
| **Long-term Memory** | PostgreSQL (LangGraph) | None |
| **Frontend Hosting** | Vercel | Vercel (same) |
| **Ingestion** | GitHub Actions | GitHub Actions or EventBridge |
| **Prompts** | LangSmith Hub | Local files |

### What We Keep from chat-langchain

- Graph architecture pattern (RetrievalGraph → ResearcherGraph)
- HTML → Markdown parsing for clean LLM context
- Document chunking strategy
- XML-formatted context for citations
- State reducers for parallel retrieval deduplication
- Frontend UI (Next.js)

### What We Simplify

- No runtime model configuration (hardcoded)
- No Redis (no thread persistence needed)
- No separate record manager database (use same RDS)
- No multi-provider LLM support
- Prompts stored locally instead of LangSmith Hub

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM ARCHITECTURE                                │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         FRONTEND (Vercel)                            │   │
│   │                                                                      │   │
│   │   Next.js Application                                                │   │
│   │   - Chat UI                                                          │   │
│   │   - SSE streaming display                                            │   │
│   │   - Source citations                                                 │   │
│   │                                                                      │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│                                  │ HTTPS + SSE                              │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         AWS INFRASTRUCTURE                           │   │
│   │                                                                      │   │
│   │   ┌─────────────────┐                                               │   │
│   │   │   ALB (HTTPS)   │  Application Load Balancer                    │   │
│   │   │   + ACM Cert    │  - SSL termination                            │   │
│   │   └────────┬────────┘  - Health checks                              │   │
│   │            │                                                         │   │
│   │            ▼                                                         │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │                   ECS Fargate Service                        │   │   │
│   │   │                                                              │   │   │
│   │   │   ┌────────────────┐        ┌────────────────┐              │   │   │
│   │   │   │    Task 1      │        │    Task 2      │   min: 2     │   │   │
│   │   │   │                │        │                │   tasks      │   │   │
│   │   │   │  ┌──────────┐  │        │  ┌──────────┐  │              │   │   │
│   │   │   │  │ FastAPI  │  │        │  │ FastAPI  │  │              │   │   │
│   │   │   │  │   +      │  │        │  │   +      │  │              │   │   │
│   │   │   │  │LangGraph │  │        │  │LangGraph │  │              │   │   │
│   │   │   │  └──────────┘  │        │  └──────────┘  │              │   │   │
│   │   │   └───────┬────────┘        └───────┬────────┘              │   │   │
│   │   │           │                         │                        │   │   │
│   │   └───────────┼─────────────────────────┼────────────────────────┘   │   │
│   │               │                         │                            │   │
│   │               └────────────┬────────────┘                            │   │
│   │                            │                                         │   │
│   │                            ▼                                         │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │              RDS PostgreSQL + pgvector                       │   │   │
│   │   │                                                              │   │   │
│   │   │   ┌──────────────────┐    ┌──────────────────┐              │   │   │
│   │   │   │  vectors         │    │  record_manager  │              │   │   │
│   │   │   │  (embeddings)    │    │  (deduplication) │              │   │   │
│   │   │   └──────────────────┘    └──────────────────┘              │   │   │
│   │   │                                                              │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        EXTERNAL SERVICES                             │   │
│   │                                                                      │   │
│   │   ┌────────────┐    ┌────────────┐    ┌────────────┐                │   │
│   │   │  OpenAI    │    │ LangSmith  │    │  Source    │                │   │
│   │   │  API       │    │ (tracing)  │    │  Website   │                │   │
│   │   │            │    │            │    │  (posts)   │                │   │
│   │   └────────────┘    └────────────┘    └────────────┘                │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Backend API (FastAPI + LangGraph)

**Technology Stack:**
- FastAPI for HTTP API
- LangGraph for orchestration
- langchain-openai for LLM calls
- langchain-postgres for pgvector
- SQLAlchemy for database access

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check for ALB |
| `/chat` | POST | Stateless chat with streaming response |
| `/chat/stream` | POST | SSE streaming endpoint |

**Configuration (Environment Variables):**

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini  # Hardcoded default

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/chatbot

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=chatbot-prod

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small
```

### 2. Vector Database (PostgreSQL + pgvector)

**Why pgvector over Weaviate:**

| Aspect | pgvector | Weaviate |
|--------|----------|----------|
| Infrastructure | Single RDS instance | Separate managed service |
| Cost | ~$15-30/mo (RDS) | ~$45+/mo (Weaviate Cloud) |
| Complexity | Lower (one database) | Higher (separate system) |
| Features | Basic vector search | Hybrid search, modules |
| ACID | Full support | Limited |

**Schema:**

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table with embeddings
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    metadata JSONB,
    source TEXT,
    title TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- HNSW index for fast similarity search
CREATE INDEX ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Record manager table (for deduplication)
CREATE TABLE record_manager (
    id SERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    namespace TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    group_id TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3. Compute (ECS Fargate)

**Why Fargate over Lambda/App Runner:**

| Factor | Lambda | ECS Fargate | App Runner |
|--------|--------|-------------|------------|
| Cold starts | 3-5s (LangChain imports) | None | ~1-2s |
| Streaming | Limited SSE support | Full SSE | Full SSE |
| Timeout | 15 min max | Unlimited | **120s hard limit** |
| DB pooling | Needs RDS Proxy | Native | Native |
| Cost (moderate) | Variable | ~$35/mo | ~$25/mo |

**Task Definition:**

```yaml
# Fargate task configuration
cpu: 512        # 0.5 vCPU
memory: 1024    # 1 GB RAM
minTasks: 2     # High availability
maxTasks: 10    # Auto-scaling limit

# Container configuration
containerPort: 8080
healthCheck:
  path: /health
  interval: 30s
  timeout: 5s
  startPeriod: 60s  # Allow time for LangChain imports
```

### 4. Frontend (Vercel)

Reuse the chat-langchain Next.js frontend with minimal modifications:

**Required Changes:**
- Update `API_BASE_URL` to point to ALB endpoint
- Remove model selection UI (hardcoded backend)
- Update branding/styling as needed

**Environment Variables (Vercel):**

```bash
API_BASE_URL=https://api.your-domain.com
NEXT_PUBLIC_API_URL=https://api.your-domain.com
```

---

## Infrastructure

### AWS Resources

```
VPC
├── Public Subnets (2 AZs)
│   └── ALB
├── Private Subnets (2 AZs)
│   ├── ECS Fargate Tasks
│   └── RDS PostgreSQL
└── Security Groups
    ├── ALB-SG (inbound 443)
    ├── ECS-SG (inbound from ALB)
    └── RDS-SG (inbound from ECS)
```

### Infrastructure as Code

Recommended: **Terraform** or **AWS CDK**

```hcl
# Example Terraform structure
terraform/
├── main.tf
├── variables.tf
├── outputs.tf
├── modules/
│   ├── vpc/
│   ├── ecs/
│   ├── rds/
│   └── alb/
└── environments/
    ├── dev.tfvars
    └── prod.tfvars
```

---

## Ingestion Pipeline

### Data Source

- **Type:** Structured website (blog posts)
- **Format:** HTML pages with consistent structure
- **Frequency:** New posts every 1-2 weeks

### Ingestion Strategy Options

| Option | Trigger | Pros | Cons |
|--------|---------|------|------|
| **Scheduled** | EventBridge (every 2 weeks) | Simple, predictable | May miss posts, wasteful if no changes |
| **On-demand** | Webhook when post published | Real-time updates | Requires CMS integration |
| **Hybrid** | Webhook + weekly full sync | Best coverage | More complex |

**Recommendation:** Start with **scheduled** (simpler), migrate to **on-demand** when you have webhook capability.

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION PIPELINE                                   │
│                                                                             │
│   ┌───────────────┐                                                         │
│   │  Trigger      │  EventBridge Schedule OR GitHub Action                  │
│   └───────┬───────┘                                                         │
│           │                                                                 │
│           ▼                                                                 │
│   ┌───────────────┐                                                         │
│   │  SitemapLoader│  Crawl sitemap.xml                                      │
│   │  (or custom)  │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                 │
│           ▼                                                                 │
│   ┌───────────────┐                                                         │
│   │  HTML Parser  │  Extract content, convert to Markdown                   │
│   │  (custom)     │  - Remove nav, footer, scripts                          │
│   └───────┬───────┘  - Preserve headers, code blocks, links                 │
│           │                                                                 │
│           ▼                                                                 │
│   ┌───────────────┐                                                         │
│   │  Chunker      │  RecursiveCharacterTextSplitter                         │
│   │               │  - chunk_size: 4000                                     │
│   └───────┬───────┘  - chunk_overlap: 200                                   │
│           │                                                                 │
│           ▼                                                                 │
│   ┌───────────────┐                                                         │
│   │  Embeddings   │  OpenAI text-embedding-3-small                          │
│   │               │  (1536 dimensions)                                      │
│   └───────┬───────┘                                                         │
│           │                                                                 │
│           ▼                                                                 │
│   ┌───────────────┐                                                         │
│   │  Indexer      │  langchain index() with SQLRecordManager                │
│   │               │  - Deduplication by source URL                          │
│   └───────┬───────┘  - cleanup="full" removes stale docs                    │
│           │                                                                 │
│           ▼                                                                 │
│   ┌───────────────┐                                                         │
│   │  pgvector     │  Documents stored with embeddings                       │
│   │  (RDS)        │                                                         │
│   └───────────────┘                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Ingestion Options

**Option A: GitHub Actions (like chat-langchain)**

```yaml
# .github/workflows/ingest.yml
name: Ingest Documents

on:
  schedule:
    - cron: '0 0 */14 * *'  # Every 2 weeks
  workflow_dispatch:  # Manual trigger

jobs:
  ingest:
    runs-on: ubuntu-latest
    environment: Indexing
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run python -m backend.ingest
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

**Option B: AWS Lambda + EventBridge**

```python
# Lambda function for ingestion
def handler(event, context):
    from backend.ingest import run_ingestion
    run_ingestion()
    return {"status": "success"}
```

---

## Cost Estimates

### Monthly Infrastructure Costs

| Component | Configuration | Estimated Cost |
|-----------|--------------|----------------|
| **ECS Fargate** | 2 tasks × (0.5 vCPU, 1GB) | ~$35 |
| **ALB** | Base + data transfer | ~$20 |
| **RDS PostgreSQL** | db.t3.micro, 20GB | ~$15 |
| **ECR** | Container storage | ~$1 |
| **CloudWatch** | Logs + metrics | ~$5 |
| **Route 53** | Hosted zone | ~$1 |
| **ACM** | SSL certificate | Free |
| **Secrets Manager** | 4-5 secrets | ~$2 |
| **Vercel** | Frontend hosting | Free (hobby) or $20 (pro) |
| **LangSmith** | Tracing | Free tier or $39 |
| | | |
| **Infrastructure Total** | | **~$80-120/month** |

### Variable Costs (Usage-Based)

| Service | Unit Cost | Example Usage | Monthly Cost |
|---------|-----------|---------------|--------------|
| **OpenAI GPT-4o-mini** | $0.15/1M input, $0.60/1M output | 1M tokens | ~$0.75 |
| **OpenAI Embeddings** | $0.02/1M tokens | 500K tokens | ~$0.01 |
| **Data Transfer** | $0.09/GB (out) | 10GB | ~$0.90 |

### Cost Comparison: This Project vs chat-langchain

| Component | chat-langchain | This Project |
|-----------|---------------|--------------|
| LangGraph Cloud | ~$50-200/mo | $0 (self-hosted) |
| Weaviate Cloud | ~$45/mo | $0 (use pgvector) |
| Supabase | ~$25/mo | $0 (use same RDS) |
| ECS Fargate | $0 | ~$55 |
| RDS PostgreSQL | $0 | ~$15 |
| ALB | $0 | ~$20 |
| | | |
| **Total** | ~$120-270/mo | **~$90-120/mo** |

---

## Security Considerations

### Production Checklist

Based on [chat-langchain PRODUCTION.md](https://github.com/langchain-ai/chat-langchain/blob/master/PRODUCTION.md):

#### 1. Abuse Prevention

| Measure | Implementation | Priority |
|---------|---------------|----------|
| Rate limiting | API Gateway or FastAPI middleware | High |
| Request validation | Pydantic models | High |
| Input length limits | Max 4000 chars per message | Medium |
| Cost monitoring | CloudWatch alarms on OpenAI spend | High |

```python
# Example rate limiting with slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request):
    ...
```

#### 2. Prompt Injection Mitigation

| Measure | Implementation |
|---------|---------------|
| Scope LLM permissions | Read-only database access |
| Input sanitization | Strip control characters |
| Output filtering | Don't expose system prompts |
| Monitoring | Log suspicious patterns |

#### 3. Infrastructure Security

| Measure | Implementation |
|---------|---------------|
| Network isolation | Private subnets for ECS/RDS |
| Secrets management | AWS Secrets Manager |
| TLS everywhere | ALB HTTPS, RDS SSL |
| IAM least privilege | Task roles with minimal permissions |
| Security groups | Strict ingress/egress rules |

---

## Development Roadmap

### Phase 1: Foundation (Week 1-2)

- [ ] Set up AWS infrastructure (Terraform/CDK)
  - [ ] VPC with public/private subnets
  - [ ] RDS PostgreSQL with pgvector
  - [ ] ECS cluster and service
  - [ ] ALB with HTTPS
- [ ] Create FastAPI backend skeleton
  - [ ] Health endpoint
  - [ ] Basic chat endpoint
- [ ] Connect to pgvector
- [ ] Deploy to ECS (manually)

### Phase 2: Core Features (Week 3-4)

- [ ] Implement LangGraph retrieval flow
  - [ ] RetrievalGraph (parent)
  - [ ] ResearcherGraph (child)
- [ ] Implement ingestion pipeline
  - [ ] HTML parser for source website
  - [ ] Chunking and embedding
  - [ ] pgvector indexing with record manager
- [ ] Add SSE streaming
- [ ] LangSmith integration

### Phase 3: Frontend & Polish (Week 5-6)

- [ ] Fork and customize chat-langchain frontend
- [ ] Deploy frontend to Vercel
- [ ] Connect frontend to backend API
- [ ] End-to-end testing

### Phase 4: Production Hardening (Week 7-8)

- [ ] Rate limiting
- [ ] Error handling and retries
- [ ] Monitoring and alerting
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Scheduled ingestion
- [ ] Load testing
- [ ] Security review

---

## File Structure (Hexagonal Architecture)

The project follows **hexagonal architecture** (ports & adapters) to separate business logic from framework-specific implementations:

```
ai_chatbot/
├── backend/
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry point
│   │   │
│   │   ├── app/                       # APPLICATION LAYER
│   │   │   │                          # (Use cases, orchestration logic)
│   │   │   ├── __init__.py
│   │   │   ├── state.py               # State definitions (AgentState, ResearcherState)
│   │   │   │
│   │   │   └── workflow/              # Graph node logic (framework-agnostic)
│   │   │       ├── __init__.py
│   │   │       ├── nodes/             # Node functions
│   │   │       │   ├── __init__.py
│   │   │       │   ├── create_research_plan.py
│   │   │       │   ├── conduct_research.py
│   │   │       │   ├── respond.py
│   │   │       │   ├── generate_queries.py
│   │   │       │   └── retrieve_documents.py
│   │   │       ├── prompts/           # System prompts
│   │   │       │   ├── __init__.py
│   │   │       │   └── retrieval_prompts.py
│   │   │       └── utils/             # Shared utilities
│   │   │           ├── __init__.py
│   │   │           ├── reduce_docs.py
│   │   │           └── format_docs.py
│   │   │
│   │   ├── domain/                    # DOMAIN LAYER
│   │   │   │                          # (Business logic, interfaces/ports)
│   │   │   └── ports/
│   │   │       ├── __init__.py
│   │   │       ├── model_port.py      # LLM interface
│   │   │       └── retriever_port.py  # Vector store interface
│   │   │
│   │   └── infra/                     # INFRASTRUCTURE LAYER
│   │       │                          # (Framework-specific adapters)
│   │       ├── models/                # LLM adapters
│   │       │   ├── __init__.py
│   │       │   ├── model_factory.py
│   │       │   ├── openai_model.py
│   │       │   └── gemini_model.py
│   │       ├── retrievers/            # Vector store adapters
│   │       │   ├── __init__.py
│   │       │   └── pgvector_retriever.py
│   │       └── graphs/                # LangGraph wiring (framework-specific)
│   │           ├── __init__.py
│   │           ├── retrieval_graph.py
│   │           └── researcher_graph.py
│   │
│   ├── ingest/                        # Ingestion pipeline
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── parser.py
│   │   └── indexer.py
│   │
│   └── tests/
│       ├── test_api.py
│       ├── test_graph.py
│       └── test_ingestion.py
│
├── docs/                              # Documentation
│   ├── graph-state-flow.md            # State flow walkthrough
│   └── ...
│
├── frontend/                          # Forked from chat-langchain
│   └── ...
│
├── infrastructure/
│   ├── terraform/
│   │   └── ...
│   └── docker/
│       └── Dockerfile
│
├── .github/
│   └── workflows/
│       ├── deploy.yml
│       └── ingest.yml
│
├── pyproject.toml
├── uv.lock
├── .env.example
├── .pre-commit-config.yaml
├── README.md
├── architecture.md
├── implementation-guide.md
└── PROJECT-SPEC.md
```

### Layer Responsibilities

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Domain** | `domain/ports/` | Interfaces (ports) for external dependencies |
| **Application** | `app/` | Use case logic, state definitions, node logic |
| **Infrastructure** | `infra/` | Framework-specific adapters (LangGraph, OpenAI, pgvector) |

### Why Graphs in `infra/`?

The graph definitions (`StateGraph`, `add_edge`, `compile`) are **LangGraph-specific**, just like `ChatOpenAI` is OpenAI-specific. The **node logic** in `app/workflow/nodes/` is framework-agnostic and could theoretically be reused with a different orchestration framework.

---

## References

- [chat-langchain Repository](https://github.com/langchain-ai/chat-langchain)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [LangChain PostgreSQL Integration](https://python.langchain.com/docs/integrations/vectorstores/pgvector/)
- [AWS ECS Fargate Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)

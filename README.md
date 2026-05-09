# 🐒 Insight Monkey — Secure AI Insights Assistant

Insight Monkey is a state-of-the-art, secure, multi-source enterprise business intelligence and analytics assistant. Built to combine structured relational data, unstructured document text (PDFs), and uploaded spreadsheets (CSV/Excel) within high-integrity private sessions, it empowers executives and analysts to extract decision-ready insights, compute critical temporal business metrics, and generate beautiful interactive charts—all within a single private and secure AI conversation.

---

## 🏗️ Core Architecture & Data Flow

Insight Monkey is designed around two major decoupled pipelines: **Data Ingestion** and **Conversational Orchestration & Synthesis**. Both run seamlessly with full, session-scoped isolation.

### 1. Ingestion Pipeline
This pipeline standardizes and securely indexes files and databases to make them instantly accessible by specialized analytical tools:
```mermaid
flowchart TD
    subgraph Client Upload
        CSV[CSV/Excel File]
        PDF[PDF Document]
        DB_Creds[SQL Connection Credentials]
    end

    subgraph FastAPI Ingestion Routing
        CSV_Route[POST /ingest/dataset]
        PDF_Route[POST /ingest/pdf]
        DB_Route[POST /ingest/connect]
    end

    subgraph Secure Storage Engines
        PG[(Local PostgreSQL)]
        VectorDB[(FAISS Vector Embeddings)]
        Mongo[(MongoDB Registry)]
    end

    CSV -->|Optional dataset_name fallback| CSV_Route
    PDF -->|Automated parsing| PDF_Route
    DB_Creds -->|Credentials parsing| DB_Route

    CSV_Route -->|Upload to session-scoped table| PG
    CSV_Route -->|Register metadata| Mongo
    PDF_Route -->|Index text with PyTorch SentenceTransformers| VectorDB
    PDF_Route -->|Register page indexes| Mongo
    DB_Route -->|Store credentials securely| Mongo
```

### 2. Multi-Turn Stream Synthesis Pipeline
Insight Monkey utilizes a capability-driven routing engine that acts as an expert orchestrator to coordinate structured and unstructured tools:
```mermaid
flowchart TD
    UserQuery[User query or follow-up] --> HistoryFetcher[Fetch recent logs from MongoDB Chats]
    HistoryFetcher --> TiktokenBuffer[Buffer history capped to 500 tokens using tiktoken]
    TiktokenBuffer --> Orchestrator[Orchestrator Classifier & Intent Router]
    
    Orchestrator -->|Bypass if Greeting| GreetingStream[SSE Stream: Warm Intro & Capabilities]
    Orchestrator -->|Execute SQL Aggregate| ToolSQL[SQL Tools: Local/External Postgres, MySQL]
    Orchestrator -->|Execute Pandas Rolling Avg/Corr/Outliers| ToolPandas[Pandas Advanced Analytical Tools]
    Orchestrator -->|Execute RAG Citation Search| ToolRAG[FAISS Retrieval with strict citations]

    ToolSQL --> Aggregator[Multi-Source Aggregator]
    ToolPandas --> Aggregator
    ToolRAG --> Aggregator

    Aggregator --> ChartAgent[Declarative Charting Agent]
    ChartAgent -->|Persist JSON chart configs| Recharts[Recharts Interactive Visual Components]
    
    Aggregator --> Synthesizer[Executive Summary Synthesizer]
    Synthesizer -->|SSE Token Stream| UI[React Tailwind UI Chat Window]
```

---

## ⚡ Key Features

*   **Precise Conversational Memory (Tiktoken-Capped Buffer):** The Orchestrator and Synthesizer analyze recent chat interactions up to a strict **500-token window** (precisely calculated using `tiktoken` for `gpt-4o` token schemas). This lets you ask context-rich follow-ups (e.g., *"Why is Stellar Run trending?"* followed by *"Plot its rolling average"*).
*   **Conversational Greetings Bypass:** Polite queries (e.g., *"hi"*, *"hello"*, *"how can you help me"*) skip heavy database orchestration to return a warm intro of capabilities instantly.
*   **Seamless Ingestion Names:** When uploading datasets or reports, the `dataset_name` is optional. The backend automatically falls back to `file.filename` while validating case-insensitive extensions (e.g., `.pdf`, `.csv`, `.xlsx`).
*   **Connected Sources Tracker:** Access `GET /ingest/sessions/{session_id}/sources` to instantly audit all datasets, PDFs (excluding heavy text bodies), and SQL connections loaded into an active session.

---

## 🛠️ Technology Stack

| Layer | Technologies Used | Key Benefits |
| :--- | :--- | :--- |
| **Backend API** | FastAPI, Uvicorn, Python 3.11 | High performance, fully async networking, self-documenting OpenAPI. |
| **Orchestration** | OpenAI API (`gpt-4o`), `tiktoken` | Advanced tool extraction and multi-turn conversational reasoning. |
| **RAG Engine** | FAISS, PyTorch (`SentenceTransformers`) | Dense vector search with native text extraction and page citations. |
| **Relational DB** | PostgreSQL, MySQL, SQLAlchemy | Dedicated database hosts for synthetic analytics schemas. |
| **NoSQL / Logs** | MongoDB, Motor (Async) | High-speed storage for chat logs, session registries, and metrics. |
| **Frontend UI** | React 19, Vite, Tailwind CSS v4 | Rapid hot-module replacement, modern flexbox designs, premium themes. |
| **Animations** | Framer Motion | Buttery smooth transitions and micro-interactions. |
| **Data Viz** | Recharts, React-Markdown | Real-time interactive charting and structured executive summaries. |

---

## 🚀 Quick Setup & Run Guide

Insight Monkey comes fully containerized with Docker Compose to spin up your APIs, state stores, and frontend clients with a single command.

### Prerequisites
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed on your host system.
*   An active `OPENAI_API_KEY` pasted inside your `.env` file at the root directory:
    ```bash
    OPENAI_API_KEY=your_openai_api_key_here
    ```

### Running with Docker Compose (Recommended)
This command boots up **5 isolated service containers** mapped to standard internal network ports:
1.  `mongodb` (NoSQL chat logs & registry - Port 27017)
2.  `postgres` (Primary storage - Port 5432)
3.  `postgres_movies` (Movies DB - Port 5433)
4.  `postgres_automotive` (Automotive DB - Port 5434)
5.  `mysql_ecommerce` (Ecommerce DB - Port 3307)
6.  `api` (FastAPI backend - Port 8000)

```bash
# 1. Spin up all containers in detached mode
docker-compose up --build -d

# 2. Check service health
curl http://localhost:8000/health
```

---

## 📥 Ingestion & Databases Guide

### Structured SQL Databases
We host 3 pre-configured relational databases with persistent volumes. To connect to them in a session, use the **Add Data Source** form in the frontend sidebar, or send a `POST /ingest/connect_db` request with the following parameters:

#### 1. Movies Database (PostgreSQL)
*   **Host**: `postgres_movies`
*   **Port**: `5432`
*   **Database**: `movies_db`
*   **User / Password**: `movie_user` / `movie_password`
*   **Internal connection string**: `postgresql://movie_user:movie_password@postgres_movies:5432/movies_db`

#### 2. Automotive Database (PostgreSQL)
*   **Host**: `postgres_automotive`
*   **Port**: `5432`
*   **Database**: `automotive_db`
*   **User / Password**: `automotive_user` / `automotive_password`
*   **Internal connection string**: `postgresql://automotive_user:automotive_password@postgres_automotive:5432/automotive_db`

#### 3. E-Commerce Database (MySQL)
*   **Host**: `mysql_ecommerce`
*   **Port**: `3306`
*   **Database**: `ecommerce_db`
*   **User / Password**: `ecommerce_user` / `ecommerce_password`
*   **Internal connection string**: `mysql+pymysql://ecommerce_user:ecommerce_password@mysql_ecommerce:3306/ecommerce_db`

*Note: Port mappings on your local localhost are slightly shifted (e.g., `5433`, `5434`, `3307`) to prevent local driver conflicts. If connecting from an external tool like DBeaver, use those ports.*

---

## 📊 Business Analyst How-To Guide

Here is a typical flow of how to use **Insight Monkey** to analyze data from scratch:

### 1. Start a Session & Upload Documents
1. Open the UI or trigger `POST /ingest/dataset` with a CSV or Excel spreadsheet (such as `marketing_spend.csv` or `regional_performance.csv`).
2. Upload unstructured PDFs via `POST /ingest/pdf` (such as `quarterly_report.pdf`).
3. View all loaded files and registries by querying `GET /ingest/sessions/{session_id}/sources`.

### 2. Connect Your SQL Databases
1. Connect a database (e.g. Movies DB) to your session by submitting its credentials to the connection router.
2. The orchestrator automatically introspects the table schemas and lists them instantly for query routing.

### 3. Ask Context-Rich Questions
Ask questions in the chat window, such as:
*   *"Which titles performed best in 2025 according to our quarterly report?"* (Routes to FAISS RAG, provides page citations)
*   *"Can you plot a rolling average of marketing spend?"* (Routes to Pandas analytical tools, generates interactive chart)
*   *"Is there a correlation between CTR and sales conversions?"* (Routes to cross-dataset correlation joiner)

---

## 🔒 Assumptions & Architectural Tradeoffs

*   **Vector Search Scope**: FAISS indexes are stored in-memory per API deployment context, paired with MongoDB for persistence. This guarantees blazing-fast retrieval speeds without the cost of remote vector database calls.
*   **Pandas-in-Worker Execution**: Standard analytical calculations (correlation coefficients, rolling trends, outlier detection) run in isolated Python processes using Pandas, keeping the primary SQL database free of heavy statistical computation overhead.
*   **Session Isolation**: Data is separated securely using session IDs. Deleting a session clears all connected datasets from PostgreSQL, text indexes from MongoDB, and its entire conversational chat log cleanly.

---

*Insight Monkey is crafted with 💖 to deliver secure, explainable, and lightning-fast enterprise intelligence.*

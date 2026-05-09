# 🔌 External SQL Database Connections & Credentials

This document outlines the exact fields and connection credentials requested by the **"Add Data Source"** modal inside the Insight Monkey frontend sidebar.

Choose the parameters below depending on how you are running the system:
* **External (Local Machine / GUI Tools)**: Use these if running the backend outside Docker (e.g. locally in terminal) or connecting via a database management GUI (like DBeaver or pgAdmin).
* **Internal (Docker Network)**: Use these if running both the backend and database services inside the same Docker Compose network context.

---

## 🎬 1. Movies Database (PostgreSQL)

### Option A: External (Local Machine / GUI / Local Backend Host)
* **Source Type**: `PostgreSQL Database`
* **Host**: `localhost`
* **Port**: `5433`
* **Database Name**: `movies_db`
* **Username**: `movie_user`
* **Password**: `movie_password`

### Option B: Internal (Docker Network Context)
* **Source Type**: `PostgreSQL Database`
* **Host**: `postgres_movies`
* **Port**: `5432`
* **Database Name**: `movies_db`
* **Username**: `movie_user`
* **Password**: `movie_password`

---

## 🚗 2. Automotive Database (PostgreSQL)

### Option A: External (Local Machine / GUI / Local Backend Host)
* **Source Type**: `PostgreSQL Database`
* **Host**: `localhost`
* **Port**: `5434`
* **Database Name**: `automotive_db`
* **Username**: `automotive_user`
* **Password**: `automotive_password`

### Option B: Internal (Docker Network Context)
* **Source Type**: `PostgreSQL Database`
* **Host**: `postgres_automotive`
* **Port**: `5432`
* **Database Name**: `automotive_db`
* **Username**: `automotive_user`
* **Password**: `automotive_password`

---

## 🛒 3. Ecommerce Database (MySQL)

### Option A: External (Local Machine / GUI / Local Backend Host)
* **Source Type**: `MySQL Database`
* **Host**: `localhost`
* **Port**: `3307`
* **Database Name**: `ecommerce_db`
* **Username**: `ecommerce_user`
* **Password**: `ecommerce_password`

### Option B: Internal (Docker Network Context)
* **Source Type**: `MySQL Database`
* **Host**: `mysql_ecommerce`
* **Port**: `3306`
* **Database Name**: `ecommerce_db`
* **Username**: `ecommerce_user`
* **Password**: `ecommerce_password`

# Bulk Certificate Generator API (Supabase Integration)

A high-performance, fault-tolerant backend API built with **Python**, **FastAPI**, and **Supabase** (`supabase-py`) to generate professional PDF certificates in bulk from a predefined template.

---

## Features

- **Bulk Job Processing:** Accepts batches of recipients in a single request and processes generation asynchronously in the background.
- **Strict Input Validation:** Powered by Pydantic; validates email format, non-empty fields, and payload schema before accepting jobs.
- **Native Supabase Client:** Directly interacts with your Supabase database tables (`generation_jobs` and `certificates`) using the official `supabase-py` SDK (`supabase.table(...).insert()`, `.select()`, `.update()`).
- **Fault-Tolerant Generation:** Individual certificate generation failures (e.g., corrupted data or rendering issues) are isolated and recorded without aborting the rest of the batch.
- **Real-Time Progress Tracking:** Tracks job execution lifecycle (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `PARTIALLY_FAILED`, `FAILED`) with live counters and percentage completion.
- **Dual Retrieval Options:** Download individual PDF certificates or download all certificates for a job in a single `.zip` archive.
- **Interactive API Documentation:** Built-in Swagger UI (`/docs`) and ReDoc (`/redoc`).

---

## Supabase Database Schema

To set up your tables in your Supabase project, execute the following SQL in the **Supabase SQL Editor**:

```sql
-- 1. Create generation_jobs table
create table public.generation_jobs (
    id text primary key,
    event_name text not null,
    issue_date text not null,
    status text not null default 'PENDING',
    total_count int not null default 0,
    success_count int not null default 0,
    failed_count int not null default 0,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 2. Create certificates table
create table public.certificates (
    id text primary key,
    job_id text not null references public.generation_jobs(id) on delete cascade,
    recipient_name text not null,
    recipient_email text not null,
    custom_title text,
    status text not null default 'PENDING',
    file_path text,
    error_message text,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);
```

---

## Architecture & Design Decisions

### 1. Framework: FastAPI
- **Asynchronous Architecture:** Handles concurrent API requests without blocking.
- **Background Tasks:** Offloads CPU/IO-heavy PDF generation out of the HTTP request cycle using FastAPI's `BackgroundTasks`. The client immediately receives `202 Accepted` with a `job_id`, preventing HTTP timeout on large recipient lists.
- **Automatic Documentation:** Generates interactive OpenAPI Swagger UI at `/docs`.

### 2. Database: Supabase Client SDK (`supabase-py`)
- Employs the official `supabase` Python SDK (`create_client(SUPABASE_URL, SUPABASE_KEY)`).
- Interacts with PostgREST REST APIs for seamless cloud database operations.
- Includes an in-memory client fallback so automated tests and offline runs execute without requiring live cloud credentials.

### 3. Rendering Engine: ReportLab
- Generates high-resolution, vector-based PDF certificates using a predefined professional landscape template (letter size: 11" x 8.5").
- Pure-Python implementation: does not require heavy external headless browser binaries (e.g., Puppeteer, Chromium, wkhtmltopdf).

### 4. Fault Isolation Strategy
- When processing a job, each recipient certificate is wrapped in an isolated `try/except` block.
- If rendering fails for one recipient, the error reason is saved into `certificates.error_message`, the status is marked `FAILED`, `failed_count` is incremented, and processing immediately proceeds to the remaining recipients.
- The job status reflects this: if some succeed and some fail, the job ends with `PARTIALLY_FAILED`.

---

## Project Structure

```
Bulk Certificate Generator/
├── app/
│   ├── __init__.py
│   ├── config.py             # Supabase URL & Key configuration
│   ├── database.py           # Supabase client provider with in-memory fallback
│   ├── models.py             # Status enums (JobStatus, CertificateStatus)
│   ├── schemas.py            # Pydantic validation schemas & API models
│   ├── generator.py          # ReportLab predefined certificate PDF generator
│   ├── tasks.py              # Background worker with fault isolation (Supabase SDK)
│   ├── main.py               # FastAPI entrypoint, middleware, health endpoints
│   └── routers/
│       ├── __init__.py
│       └── jobs.py           # REST API endpoints (Supabase queries)
├── tests/
│   ├── __init__.py
│   └── test_certificates.py  # Comprehensive test suite covering all requirements
├── .env.example              # Sample configuration for Supabase API keys
├── requirements.txt          # Project dependencies (FastAPI, Supabase, ReportLab, etc.)
└── README.md                 # Complete documentation
```

---

## Getting Started

### 1. Installation
Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your credentials from the **Supabase Dashboard** -> **Project Settings** -> **API**:
```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-role-key
```

---

## Running the Application

Start the local server using `uvicorn`:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

- **API Base URL:** `http://127.0.0.1:8000`
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## Running Automated Tests

Run the test suite using `pytest`:
```bash
python -m pytest -v
```

All 8 tests validate job creation, input validation, Supabase operations, error fault tolerance, and single/bulk downloads.

---

## API Usage Guide

### 1. Submit a Bulk Certificate Generation Request
- **Endpoint:** `POST /api/v1/jobs`
- **Response Code:** `202 Accepted`

**Request Body:**
```json
{
  "event_name": "Full Stack Cloud Summit 2026",
  "issue_date": "2026-10-15",
  "recipients": [
    {
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice@example.com",
      "custom_title": "Lead Engineer"
    },
    {
      "recipient_name": "Bob Smith",
      "recipient_email": "bob@example.com"
    }
  ]
}
```

**Response:**
```json
{
  "message": "Certificate generation job accepted and scheduled for processing.",
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "PENDING",
  "total_recipients": 2
}
```

---

### 2. Check Job Status & Progress
- **Endpoint:** `GET /api/v1/jobs/{job_id}`

**Response:**
```json
{
  "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "event_name": "Full Stack Cloud Summit 2026",
  "issue_date": "2026-10-15",
  "status": "COMPLETED",
  "total_count": 2,
  "success_count": 2,
  "failed_count": 0,
  "progress_percentage": 100.0,
  "created_at": "2026-10-11T15:20:00Z",
  "updated_at": "2026-10-11T15:20:02Z"
}
```

---

### 3. Check Job Details with Individual Recipient Results
- **Endpoint:** `GET /api/v1/jobs/{job_id}/details`

---

### 4. Download an Individual Certificate PDF
- **Endpoint:** `GET /api/v1/certificates/{certificate_id}/download`
- **Response:** PDF file stream (`application/pdf`)

---

### 5. Download All Certificates as a ZIP Archive
- **Endpoint:** `GET /api/v1/jobs/{job_id}/download-all`
- **Response:** ZIP archive (`application/zip`)

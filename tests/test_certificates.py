import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import set_supabase_client, InMemorySupabaseMock
import app.tasks as tasks_module

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_mock_supabase():
    mock_db = InMemorySupabaseMock()
    set_supabase_client(mock_db)
    yield mock_db


# =========================================================================
# TEST 1: Creating a Generation Job
# =========================================================================
def test_create_generation_job():
    payload = {
        "event_name": "Full Stack Cloud Workshop",
        "issue_date": "2026-10-15",
        "recipients": [
            {"recipient_name": "Alice Smith", "recipient_email": "alice@example.com"},
            {"recipient_name": "Bob Jones", "recipient_email": "bob@example.com"},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["total_recipients"] == 2
    assert data["status"] == "PENDING"


# =========================================================================
# TEST 2: Input Validation
# =========================================================================
def test_input_validation_empty_recipients():
    payload = {
        "event_name": "Empty Event",
        "issue_date": "2026-10-15",
        "recipients": [],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_input_validation_invalid_email():
    payload = {
        "event_name": "Workshop",
        "issue_date": "2026-10-15",
        "recipients": [
            {"recipient_name": "Charlie", "recipient_email": "not-an-email"},
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_input_validation_blank_name():
    payload = {
        "event_name": "Workshop",
        "issue_date": "2026-10-15",
        "recipients": [
            {"recipient_name": "   ", "recipient_email": "charlie@example.com"},
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


# =========================================================================
# TEST 3: Certificate Generation & Job Status/Progress
# =========================================================================
def test_certificate_generation_and_progress_tracking():
    payload = {
        "event_name": "Python Mastery",
        "issue_date": "2026-10-20",
        "recipients": [
            {"recipient_name": "David Miller", "recipient_email": "david@example.com"},
            {"recipient_name": "Emma Watson", "recipient_email": "emma@example.com"},
        ],
    }

    create_res = client.post("/api/v1/jobs", json=payload)
    assert create_res.status_code == 202
    job_id = create_res.json()["job_id"]

    # Check job status after TestClient background task execution
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "COMPLETED"
    assert status_data["total_count"] == 2
    assert status_data["success_count"] == 2
    assert status_data["failed_count"] == 0
    assert status_data["progress_percentage"] == 100.0


# =========================================================================
# TEST 4: Fault Tolerance - Handling an Individual Certificate Failure
# =========================================================================
def test_individual_certificate_failure_handling(monkeypatch):
    payload = {
        "event_name": "Data Engineering Summit",
        "issue_date": "2026-10-25",
        "recipients": [
            {"recipient_name": "Good Recipient 1", "recipient_email": "good1@example.com"},
            {"recipient_name": "Faulty Recipient", "recipient_email": "faulty@example.com"},
            {"recipient_name": "Good Recipient 2", "recipient_email": "good2@example.com"},
        ],
    }

    # Mock generator to deliberately raise an exception ONLY for the faulty recipient
    original_gen = tasks_module.generate_certificate_pdf

    def faulty_generator(*args, **kwargs):
        if kwargs.get("recipient_name") == "Faulty Recipient":
            raise RuntimeError("Simulated render engine fault for faulty recipient")
        return original_gen(*args, **kwargs)

    monkeypatch.setattr(tasks_module, "generate_certificate_pdf", faulty_generator)

    create_res = client.post("/api/v1/jobs", json=payload)
    assert create_res.status_code == 202
    job_id = create_res.json()["job_id"]

    # Verify job status captures partial failure and didn't crash
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200
    job_data = status_res.json()
    assert job_data["status"] == "PARTIALLY_FAILED"
    assert job_data["total_count"] == 3
    assert job_data["success_count"] == 2
    assert job_data["failed_count"] == 1
    assert job_data["progress_percentage"] == 100.0

    # Verify individual certificate statuses
    details_res = client.get(f"/api/v1/jobs/{job_id}/details")
    assert details_res.status_code == 200
    certs = details_res.json()["certificates"]

    faulty_cert = next(c for c in certs if c["recipient_name"] == "Faulty Recipient")
    assert faulty_cert["status"] == "FAILED"
    assert "Simulated render engine fault" in faulty_cert["error_message"]

    success_certs = [c for c in certs if c["recipient_name"] != "Faulty Recipient"]
    assert len(success_certs) == 2
    for sc in success_certs:
        assert sc["status"] == "SUCCESS"
        assert sc["error_message"] is None


# =========================================================================
# TEST 5: Retrieving Generated Certificates (Single Download & Bulk ZIP)
# =========================================================================
def test_retrieving_generated_certificates():
    payload = {
        "event_name": "AI Bootcamp",
        "issue_date": "2026-11-01",
        "recipients": [
            {"recipient_name": "Grace Hopper", "recipient_email": "grace@example.com"},
        ],
    }

    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]

    # Fetch certificate details to get the ID
    details_res = client.get(f"/api/v1/jobs/{job_id}/details")
    cert_id = details_res.json()["certificates"][0]["id"]

    # 1. Download single certificate
    dl_res = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert len(dl_res.content) > 0
    assert dl_res.content.startswith(b"%PDF")

    # 2. Download all certificates in a ZIP
    zip_res = client.get(f"/api/v1/jobs/{job_id}/download-all")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
        file_list = zf.namelist()
        assert len(file_list) == 1
        assert file_list[0].endswith(".pdf")
        assert "Grace_Hopper" in file_list[0]


def test_download_nonexistent_certificate():
    res = client.get("/api/v1/certificates/nonexistent-id/download")
    assert res.status_code == 404

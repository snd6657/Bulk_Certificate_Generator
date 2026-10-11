import io
import os
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, status, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.database import get_supabase_client
from app.models import JobStatus, CertificateStatus
from app.schemas import (
    CertificateGenerationRequest,
    JobCreationResponse,
    JobSummaryResponse,
    JobDetailResponse,
    CertificateResponse,
)
from app.tasks import process_certificate_job

router = APIRouter(prefix="/api/v1", tags=["Certificates"])


def calculate_progress(total: int, success: int, failed: int) -> float:
    if total <= 0:
        return 0.0
    return round(((success + failed) / total) * 100, 2)


@router.post(
    "/jobs",
    response_model=JobCreationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit bulk certificate generation request",
    description="Accepts event details and recipients, validates input, stores records in Supabase, and schedules background processing.",
)
def create_generation_job(
    payload: CertificateGenerationRequest,
    background_tasks: BackgroundTasks,
):
    supabase = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    job_id = str(uuid.uuid4())

    job_data = {
        "id": job_id,
        "event_name": payload.event_name,
        "issue_date": payload.issue_date,
        "status": JobStatus.PENDING.value,
        "total_count": len(payload.recipients),
        "success_count": 0,
        "failed_count": 0,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    # Insert job into Supabase
    supabase.table("generation_jobs").insert(job_data).execute()

    # Insert certificates into Supabase
    certificates_data = [
        {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "recipient_name": item.recipient_name,
            "recipient_email": str(item.recipient_email),
            "custom_title": item.custom_title,
            "status": CertificateStatus.PENDING.value,
            "file_path": None,
            "error_message": None,
            "created_at": now_iso,
        }
        for item in payload.recipients
    ]
    supabase.table("certificates").insert(certificates_data).execute()

    # Trigger background worker
    background_tasks.add_task(process_certificate_job, job_id)

    return JobCreationResponse(
        message="Certificate generation job accepted and scheduled for processing.",
        job_id=job_id,
        status=JobStatus.PENDING.value,
        total_recipients=len(payload.recipients),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobSummaryResponse,
    summary="Get job status and progress",
    description="Retrieve execution status, counts (success/failed/total), and progress percentage from Supabase.",
)
def get_job_status(job_id: str):
    supabase = get_supabase_client()
    res = supabase.table("generation_jobs").select("*").eq("id", job_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job with ID '{job_id}' not found.")

    job = res.data[0]
    total = int(job.get("total_count", 0))
    success = int(job.get("success_count", 0))
    failed = int(job.get("failed_count", 0))

    return JobSummaryResponse(
        id=job["id"],
        event_name=job["event_name"],
        issue_date=job["issue_date"],
        status=job["status"],
        total_count=total,
        success_count=success,
        failed_count=failed,
        progress_percentage=calculate_progress(total, success, failed),
        created_at=str(job["created_at"]),
        updated_at=str(job["updated_at"]),
    )


@router.get(
    "/jobs/{job_id}/details",
    response_model=JobDetailResponse,
    summary="Get job status with full certificate details",
    description="Retrieve the job status along with all individual recipient certificate generation results from Supabase.",
)
def get_job_details(job_id: str):
    supabase = get_supabase_client()
    job_res = supabase.table("generation_jobs").select("*").eq("id", job_id).execute()
    if not job_res.data:
        raise HTTPException(status_code=404, detail=f"Job with ID '{job_id}' not found.")

    job = job_res.data[0]
    certs_res = supabase.table("certificates").select("*").eq("job_id", job_id).execute()
    certificates = certs_res.data or []

    total = int(job.get("total_count", 0))
    success = int(job.get("success_count", 0))
    failed = int(job.get("failed_count", 0))

    return JobDetailResponse(
        id=job["id"],
        event_name=job["event_name"],
        issue_date=job["issue_date"],
        status=job["status"],
        total_count=total,
        success_count=success,
        failed_count=failed,
        progress_percentage=calculate_progress(total, success, failed),
        created_at=str(job["created_at"]),
        updated_at=str(job["updated_at"]),
        certificates=certificates,
    )


@router.get(
    "/jobs/{job_id}/certificates",
    response_model=List[CertificateResponse],
    summary="List certificates for a job",
    description="List recipient certificates associated with a job from Supabase.",
)
def list_job_certificates(
    job_id: str,
    status_filter: Optional[CertificateStatus] = Query(None, alias="status"),
):
    supabase = get_supabase_client()
    job_res = supabase.table("generation_jobs").select("*").eq("id", job_id).execute()
    if not job_res.data:
        raise HTTPException(status_code=404, detail=f"Job with ID '{job_id}' not found.")

    query = supabase.table("certificates").select("*").eq("job_id", job_id)
    if status_filter:
        query = query.eq("status", status_filter.value)

    res = query.execute()
    return res.data or []


@router.get(
    "/certificates/{certificate_id}/download",
    summary="Download an individual certificate PDF",
    description="Download a specific generated certificate PDF by certificate ID.",
)
def download_certificate(certificate_id: str):
    supabase = get_supabase_client()
    res = supabase.table("certificates").select("*").eq("id", certificate_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Certificate not found.")

    cert = res.data[0]
    if cert["status"] != CertificateStatus.SUCCESS.value:
        raise HTTPException(
            status_code=400,
            detail=f"Certificate cannot be downloaded because its status is '{cert['status']}'. Reason: {cert.get('error_message') or 'Still processing or failed.'}",
        )

    file_path = cert.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Certificate file not found on disk.")

    safe_name = "".join(c for c in cert["recipient_name"] if c.isalnum() or c in (" ", "_", "-")).rstrip()
    filename = f"{safe_name}_certificate.pdf".replace(" ", "_")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.get(
    "/jobs/{job_id}/download-all",
    summary="Download all generated certificates as a ZIP",
    description="Bundles all successfully generated certificates for a job into a single downloadable .ZIP archive.",
)
def download_all_certificates(job_id: str):
    supabase = get_supabase_client()
    job_res = supabase.table("generation_jobs").select("*").eq("id", job_id).execute()
    if not job_res.data:
        raise HTTPException(status_code=404, detail=f"Job with ID '{job_id}' not found.")

    job = job_res.data[0]
    certs_res = (
        supabase.table("certificates")
        .select("*")
        .eq("job_id", job_id)
        .eq("status", CertificateStatus.SUCCESS.value)
        .execute()
    )
    successful_certs = certs_res.data or []
    valid_files = [c for c in successful_certs if c.get("file_path") and os.path.exists(c["file_path"])]

    if not valid_files:
        raise HTTPException(
            status_code=400,
            detail=f"No generated certificates are available to download for job '{job_id}'. Current job status is '{job['status']}'.",
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for cert in valid_files:
            file_path = Path(cert["file_path"])
            arcname = f"{cert['recipient_name'].replace(' ', '_')}_{cert['id'][:8]}.pdf"
            zf.write(file_path, arcname=arcname)

    zip_buffer.seek(0)
    safe_event_name = "".join(c for c in job["event_name"] if c.isalnum() or c in (" ", "_", "-")).rstrip()
    zip_filename = f"{safe_event_name}_certificates.zip".replace(" ", "_")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )

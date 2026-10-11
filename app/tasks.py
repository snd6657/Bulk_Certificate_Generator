import logging
from datetime import datetime, timezone
from pathlib import Path
from app.config import CERTIFICATES_DIR
from app.database import get_supabase_client
from app.models import JobStatus, CertificateStatus
from app.generator import generate_certificate_pdf

logger = logging.getLogger(__name__)


def process_certificate_job(job_id: str) -> None:
    """
    Background worker function that processes a certificate generation job
    using the official Supabase Python client.
    """
    supabase = get_supabase_client()
    try:
        # Fetch job record from Supabase
        job_res = supabase.table("generation_jobs").select("*").eq("id", job_id).execute()
        if not job_res.data:
            logger.error(f"Job {job_id} not found in Supabase.")
            return

        job = job_res.data[0]

        # Update status to IN_PROGRESS
        supabase.table("generation_jobs").update({
            "status": JobStatus.IN_PROGRESS.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()

        job_dir = CERTIFICATES_DIR / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        # Fetch pending certificates for this job
        certs_res = (
            supabase.table("certificates")
            .select("*")
            .eq("job_id", job_id)
            .eq("status", CertificateStatus.PENDING.value)
            .execute()
        )
        certificates = certs_res.data or []

        success_count = int(job.get("success_count", 0))
        failed_count = int(job.get("failed_count", 0))

        for cert in certificates:
            cert_id = cert["id"]
            recip_name = cert["recipient_name"]
            try:
                safe_name = "".join(c for c in recip_name if c.isalnum() or c in (" ", "_", "-")).rstrip()
                safe_name = safe_name.replace(" ", "_")
                filename = f"{cert_id}_{safe_name}.pdf"
                dest_path = job_dir / filename

                # Generate the vector PDF certificate
                generate_certificate_pdf(
                    output_path=dest_path,
                    recipient_name=recip_name,
                    event_name=job["event_name"],
                    issue_date=job["issue_date"],
                    certificate_id=cert_id,
                    custom_title=cert.get("custom_title"),
                )

                # Update certificate record in Supabase
                supabase.table("certificates").update({
                    "status": CertificateStatus.SUCCESS.value,
                    "file_path": str(dest_path),
                    "error_message": None,
                }).eq("id", cert_id).execute()

                success_count += 1

            except Exception as exc:
                logger.exception(f"Failed generating certificate for {recip_name} ({cert_id}): {exc}")
                supabase.table("certificates").update({
                    "status": CertificateStatus.FAILED.value,
                    "file_path": None,
                    "error_message": str(exc),
                }).eq("id", cert_id).execute()

                failed_count += 1

            # Update job progress counts in Supabase in real-time
            supabase.table("generation_jobs").update({
                "success_count": success_count,
                "failed_count": failed_count,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", job_id).execute()

        # Update final job state
        if failed_count == 0:
            final_status = JobStatus.COMPLETED.value
        elif success_count == 0:
            final_status = JobStatus.FAILED.value
        else:
            final_status = JobStatus.PARTIALLY_FAILED.value

        supabase.table("generation_jobs").update({
            "status": final_status,
            "success_count": success_count,
            "failed_count": failed_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()

    except Exception as exc:
        logger.exception(f"Unhandled error in job processing worker {job_id}: {exc}")
        try:
            supabase.table("generation_jobs").update({
                "status": JobStatus.FAILED.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", job_id).execute()
        except Exception:
            pass

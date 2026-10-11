from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


class RecipientInput(BaseModel):
    recipient_name: str = Field(..., min_length=1, max_length=255, description="Full name of recipient")
    recipient_email: EmailStr = Field(..., description="Valid recipient email address")
    custom_title: Optional[str] = Field(None, max_length=255, description="Optional custom title or role")

    @field_validator("recipient_name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("recipient_name cannot be blank or whitespace only")
        return stripped


class CertificateGenerationRequest(BaseModel):
    event_name: str = Field(..., min_length=1, max_length=255, description="Event or course name")
    issue_date: str = Field(..., min_length=1, max_length=50, description="Date printed on certificate (e.g. 2026-10-11)")
    recipients: List[RecipientInput] = Field(..., min_length=1, description="List of recipient entries")

    @field_validator("event_name", "issue_date")
    @classmethod
    def fields_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be blank or whitespace only")
        return stripped


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    custom_title: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: str


class JobSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_name: str
    issue_date: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    progress_percentage: float
    created_at: str
    updated_at: str


class JobDetailResponse(JobSummaryResponse):
    model_config = ConfigDict(from_attributes=True)

    certificates: List[CertificateResponse] = []


class JobCreationResponse(BaseModel):
    message: str
    job_id: str
    status: str
    total_recipients: int

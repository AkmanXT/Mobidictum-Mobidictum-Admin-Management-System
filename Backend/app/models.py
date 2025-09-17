from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums
class CodeStatus(str, Enum):
    active = "active"
    used = "used"
    expired = "expired"
    revoked = "revoked"
    creating = "creating"
    updating = "updating"
    deleting = "deleting"
    renaming = "renaming"
    deleted = "deleted"


class CodeType(str, Enum):
    discount = "discount"
    free_ticket = "free_ticket"
    upgrade = "upgrade"


class OrderStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"
    refunded = "refunded"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class LinkStatus(str, Enum):
    active = "active"
    disabled = "disabled"


# Base models
class TimestampedModel(BaseModel):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Code models
class Code(TimestampedModel):
    id: Optional[str] = None
    code: str
    type: str
    organization_id: Optional[str] = None
    status: str = "active"
    expires_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CodeCreate(BaseModel):
    code: str
    type: str
    organization_id: Optional[str] = None
    status: str = "active"
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class CodeUpdate(BaseModel):
    status: Optional[CodeStatus] = None
    discount_percent: Optional[int] = None
    discount_amount: Optional[float] = None
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


# Order models
class Order(TimestampedModel):
    id: Optional[str] = None
    external_id: str
    customer_email: str
    customer_name: Optional[str] = None
    organization_id: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str = "USD"
    status: str
    items: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    order_date: datetime = Field(default_factory=datetime.utcnow)


class OrderCreate(BaseModel):
    external_id: str
    customer_email: str
    customer_name: Optional[str] = None
    organization_id: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str = "USD"
    status: str
    items: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    order_date: Optional[datetime] = None


# Batch job models
class BatchJob(TimestampedModel):
    id: Optional[str] = None
    name: str
    job_type: str
    status: str = "pending"
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    results: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_log: Optional[List[str]] = None


class BatchJobCreate(BaseModel):
    job_type: str
    args: Optional[Dict[str, Any]] = None
    organization_id: Optional[str] = None


class BatchJobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    results: Optional[Dict[str, Any]] = None
    error_log: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Link models
class Link(TimestampedModel):
    id: Optional[str] = None
    title: str
    original_url: str
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    short_url: Optional[str] = None
    clicks: int = 0
    organization_id: Optional[str] = None


class LinkCreate(BaseModel):
    title: str
    original_url: str
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    organization_id: Optional[str] = None


# Webhook models
class ProcessedWebhook(TimestampedModel):
    id: Optional[str] = None
    event_id: str
    event_type: str
    source: str = "make"
    raw_payload: Dict[str, Any]
    received_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    status: str = "received"
    error_message: Optional[str] = None


class WebhookCreate(BaseModel):
    event_id: str
    event_type: str
    source: str = "make.com"
    raw_payload: Dict[str, Any]
    status: str = "received"


# Email models
class EmailSendRequest(BaseModel):
    to: List[str]
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    subject: str
    body: str
    html_body: Optional[str] = None


# Automation request models
class FientaCreateCodesRequest(BaseModel):
    csv_data: Optional[str] = None
    xlsx_data: Optional[str] = None
    csv_path: Optional[str] = None
    xlsx_path: Optional[str] = None
    dry_run: bool = True
    headless: bool = True


class FientaRenameCodesRequest(BaseModel):
    csv_path: Optional[str] = None
    pairs_csv_path: Optional[str] = None
    rename_prefix: Optional[str] = None
    rename_pad_length: Optional[int] = 2
    rename_start: Optional[int] = 1
    rename_limit: Optional[int] = None
    dry_run: bool = True
    headless: bool = True


class CSVDiffRequest(BaseModel):
    old_xlsx_path: str
    new_xlsx_path: str


# Action request models
class CodeCreateRequest(BaseModel):
    code: str
    type: str = "discount"
    organization_id: Optional[str] = None
    discount_percent: Optional[int] = 10
    discount_amount: Optional[float] = None
    max_uses: Optional[int] = 1
    expires_at: Optional[datetime] = None
    description: Optional[str] = None


class CodeUpdateRequest(BaseModel):
    discount_percent: Optional[int] = None
    discount_amount: Optional[float] = None
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None
    description: Optional[str] = None
    status: Optional[CodeStatus] = None


class CodeRenameRequest(BaseModel):
    new_code: str


class ActionStatusResponse(BaseModel):
    pending_actions: Dict[str, int]
    failed_actions: List[Dict[str, Any]]
    processor_status: Dict[str, Any]
    total_pending: int


# Response models
class CodeAllocateResponse(BaseModel):
    code: str
    id: str
    allocated_at: datetime


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


# Organization models (fixing existing)
class Organization(TimestampedModel):
    id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


# Email models (adding missing)
class EmailCampaign(TimestampedModel):
    id: Optional[str] = None
    name: str
    subject: str
    content: str
    template_id: Optional[str] = None
    status: str = "draft"
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    recipient_count: int = 0
    open_count: int = 0
    click_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    organization_ids: Optional[List[str]] = None


class EmailTemplate(TimestampedModel):
    id: Optional[str] = None
    name: str
    subject: str
    content: str
    template_type: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    ai_generated: bool = False


class EmailThread(TimestampedModel):
    id: Optional[str] = None
    thread_id: str
    subject: Optional[str] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    organization_id: Optional[str] = None
    classification: Optional[str] = None
    priority: str = "normal"
    participants: Optional[List[str]] = None
    labels: Optional[List[str]] = None


# Posts model
class Post(TimestampedModel):
    id: Optional[str] = None
    title: str
    content: str
    platform: str
    status: str = "draft"
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    organization_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Copy Bank model
class CopyBank(TimestampedModel):
    id: Optional[str] = None
    title: str
    content: str
    content_type: str
    category: Optional[str] = None
    ai_generated: bool = False
    performance_score: Optional[float] = None
    usage_count: int = 0
    last_used_at: Optional[datetime] = None
    tags: Optional[List[str]] = None

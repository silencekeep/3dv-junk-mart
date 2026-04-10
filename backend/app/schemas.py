from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiErrorDetail(BaseModel):
    field: str | None = None
    reason: str


class PageMeta(BaseModel):
    page: int
    page_size: int
    next_cursor: str | None = None
    total: int | None = None


class ApiMeta(BaseModel):
    request_id: str
    cache_ttl_seconds: int | None = None
    page: PageMeta | None = None


class ApiEnvelope(BaseModel):
    code: int
    message: str
    data: Any | None = None
    meta: ApiMeta | None = None
    errors: list[ApiErrorDetail] | None = None


class Money(BaseModel):
    amount_minor: int
    currency: str = 'CNY'


class MediaAsset(BaseModel):
    id: str
    kind: str
    url: str
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    mime_type: str | None = None
    sort_order: int = 0


class UserSummary(BaseModel):
    id: str
    display_name: str
    avatar_url: str | None = None
    bio: str | None = None
    location: str | None = None
    sesame_credit_score: int = 0
    vip_level: str = 'none'
    follower_count: int = 0
    following_count: int = 0
    positive_rate: float | None = None


class UserProfileDetail(BaseModel):
    id: str
    display_name: str
    avatar_url: str | None = None
    birth_date: str | None = None
    age_years: int | None = None
    bio: str | None = None
    location: str | None = None
    sesame_credit_score: int = 0
    vip_level: str = 'none'
    profile_visibility: str = 'public'
    updated_at: str | None = None


class UserProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    birth_date: str | None = None
    bio: str | None = None
    location: str | None = None
    profile_visibility: str | None = Field(default=None, pattern='^(public|friends|private)$')


class UserAddressSummary(BaseModel):
    id: str
    user_id: str
    recipient_name: str
    phone: str
    region_code: str
    address_line1: str
    address_line2: str | None = None
    is_default: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class UserAddressCreateRequest(BaseModel):
    recipient_name: str
    phone: str
    region_code: str
    address_line1: str
    address_line2: str | None = None
    is_default: bool = False


class UserAddressUpdateRequest(BaseModel):
    recipient_name: str | None = None
    phone: str | None = None
    region_code: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    is_default: bool | None = None


class AuthIdentity(BaseModel):
    id: str
    user_id: str
    kind: str
    value: str
    is_primary: bool = True
    is_verified: bool = False
    verified_at: str | None = None


class AuthSession(BaseModel):
    id: str
    user: UserSummary
    access_token: str
    access_token_expires_at: str
    refresh_token_expires_at: str
    device_name: str | None = None
    device_platform: str | None = None
    is_new_user: bool = False
    refresh_token: str | None = None


class AuthResponse(BaseModel):
    user: UserSummary
    session: AuthSession
    profile: UserProfileDetail | None = None


class CategorySummary(BaseModel):
    id: str
    parent_id: str | None = None
    name: str
    slug: str
    icon_key: str | None = None
    sort_order: int = 0
    active: bool = True
    listing_count: int = 0


class ListingSummary(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    price: Money
    original_price: Money | None = None
    status: str
    cover_media: MediaAsset | None = None
    location: str | None = None
    badges: list[str] = Field(default_factory=list)
    seller: UserSummary | None = None


class ListingSpec(BaseModel):
    spec_key: str
    spec_value: str
    sort_order: int = 0


class ListingDraftSummary(BaseModel):
    id: str
    seller_id: str
    category_id: str | None = None
    title: str
    subtitle: str | None = None
    description: str = ''
    price: Money
    original_price: Money | None = None
    status: str = 'draft'
    condition_level: str | None = None
    location_city: str | None = None
    draft_payload_json: dict[str, Any] = Field(default_factory=dict)


class Listing3DPreview(BaseModel):
    preview_status: str
    status_message: str | None = None
    viewer_url: str | None = None
    model_url: str | None = None
    model_ply_url: str | None = None
    model_sog_url: str | None = None
    log_url: str | None = None
    cover_media: MediaAsset | None = None
    is_ready: bool = False
    placeholder: dict[str, Any] = Field(default_factory=dict)


class ListingDetail(BaseModel):
    listing: ListingSummary
    media: list[MediaAsset] = Field(default_factory=list)
    seller: UserSummary | None = None
    preview_3d: Listing3DPreview | None = None
    specs: list[ListingSpec] = Field(default_factory=list)
    similar: list[ListingSummary] = Field(default_factory=list)
    inquiries: list[dict[str, Any]] = Field(default_factory=list)
    reviews: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    id: str
    listing_id: str | None = None
    other_user: UserSummary | None = None
    last_message_preview: str | None = None
    unread_count: int = 0
    updated_at: str | None = None


class ConversationMessage(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    message_type: str = 'text'
    content_text: str = ''
    asset: MediaAsset | None = None
    created_at: str
    read_at: str | None = None


class ConversationDetail(BaseModel):
    conversation: ConversationSummary
    item_preview: ListingSummary | None = None
    safety_banner: dict[str, Any] | None = None
    messages: list[ConversationMessage] = Field(default_factory=list)
    composer: dict[str, Any] | None = None


class OrderSummary(BaseModel):
    id: str
    status: str
    buyer: UserSummary | None = None
    seller: UserSummary | None = None
    item_snapshot: dict[str, Any] = Field(default_factory=dict)
    totals: dict[str, Any] = Field(default_factory=dict)
    logistics: dict[str, Any] = Field(default_factory=dict)
    can_confirm_receipt: bool = False


class OrderTimelineEvent(BaseModel):
    id: str
    order_id: str
    status: str
    event_note: str
    actor_user_id: str | None = None
    occurred_at: str


class OrderDetail(BaseModel):
    order: OrderSummary
    timeline: list[OrderTimelineEvent] = Field(default_factory=list)
    receipt: dict[str, Any] = Field(default_factory=dict)
    action_bar: list[dict[str, Any]] = Field(default_factory=list)


class ShipmentEvent(BaseModel):
    id: str
    shipment_id: str
    event_code: str
    event_text: str
    event_city: str | None = None
    occurred_at: str


class ShipmentSnapshot(BaseModel):
    id: str
    order_id: str
    carrier_name: str | None = None
    tracking_no: str | None = None
    status: str | None = None
    shipped_at: str | None = None
    estimated_delivery_at: str | None = None


class PaymentSummary(BaseModel):
    id: str
    order_id: str
    payment_method: str | None = None
    status: str | None = None
    amount: Money
    provider_ref: str | None = None


class ReviewSummary(BaseModel):
    id: str
    order_id: str
    listing_id: str | None = None
    rating: int
    tags: list[str] = Field(default_factory=list)
    content: str = ''
    media: list[MediaAsset] = Field(default_factory=list)
    anonymity_enabled: bool = False


class ReviewDraft(BaseModel):
    order_id: str
    listing_id: str | None = None
    rating: int | None = None
    tags: list[str] = Field(default_factory=list)
    content: str = ''
    media_asset_ids: list[str] = Field(default_factory=list)
    anonymity_enabled: bool = False


class ServiceCard(BaseModel):
    service_key: str
    title: str
    icon: str
    badge: str | None = None
    description: str | None = None
    destination_type: str
    destination_ref: str


class PageSection(BaseModel):
    section_type: str
    section_id: str
    title: str | None = None
    subtitle: str | None = None
    items: list[Any] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    ui_hints: dict[str, Any] = Field(default_factory=dict)


class WalletSummary(BaseModel):
    available_minor: int
    held_minor: int
    currency: str = 'CNY'
    status: str = 'active'


class WalletTransaction(BaseModel):
    id: str
    wallet_account_id: str
    transaction_type: str
    amount: Money
    reference_type: str | None = None
    reference_id: str | None = None
    status: str = 'posted'
    created_at: str


class MembershipPlan(BaseModel):
    id: str
    plan_key: str
    title: str
    price: Money
    benefits_json: list[str] = Field(default_factory=list)
    active: bool = True


class MembershipSubscription(BaseModel):
    id: str
    user_id: str
    plan: MembershipPlan
    status: str
    started_at: str
    expires_at: str | None = None


class NotificationSummary(BaseModel):
    id: str
    user_id: str
    notification_type: str
    title: str
    body: str
    entity_type: str | None = None
    entity_id: str | None = None
    read_at: str | None = None
    created_at: str


class BadgeSummary(BaseModel):
    unread_notifications: int = 0
    unread_messages: int = 0
    active_orders: int = 0
    draft_listings: int = 0


class UserStatsSummary(BaseModel):
    posts_count: int = 0
    sold_count: int = 0
    bought_count: int = 0
    liked_count: int = 0
    followers_count: int = 0
    following_count: int = 0
    positive_rate: float | None = None
    sesame_credit_score: int = 0
    vip_level: str = 'none'


class HealthPayload(BaseModel):
    status: str = 'ok'
    version: str
    database_ready: bool = True
    demo_user_id: str
    seeded_users: int
    seeded_listings: int


HealthResponse = HealthPayload


class VersionPayload(BaseModel):
    api_version: str
    build_version: str
    service_name: str


class PublicConfigPayload(BaseModel):
    api_version: str
    base_currency: str = 'CNY'
    guest_entry_enabled: bool = True
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    supported_locales: list[str] = Field(default_factory=lambda: ['zh-CN', 'en-US'])


class AuthRegisterRequest(BaseModel):
    display_name: str
    identifier: str
    password: str
    device_name: str | None = None
    device_platform: str | None = None
    consent_version: str = 'v1'


class AuthLoginRequest(BaseModel):
    identifier: str
    password: str
    device_name: str | None = None
    device_platform: str | None = None


class AuthRefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    access_token: str | None = None


class UploadPresignRequest(BaseModel):
    filename: str
    content_type: str | None = None
    kind: str = Field(default='image', pattern='^(image|video|document)$')


class UploadPresignResponse(BaseModel):
    asset_id: str
    upload_url: str
    public_url: str
    method: str = 'PUT'
    headers: dict[str, str] = Field(default_factory=dict)
    expires_at: str


class ListingDraftCreateRequest(BaseModel):
    title: str
    subtitle: str | None = None
    description: str = ''
    category_id: str | None = None
    price_minor: int = 0
    original_price_minor: int | None = None
    currency: str = 'CNY'
    condition_level: str | None = None
    location_city: str | None = None
    draft_payload_json: dict[str, Any] = Field(default_factory=dict)


class ListingDraftUpdateRequest(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    category_id: str | None = None
    price_minor: int | None = None
    original_price_minor: int | None = None
    currency: str | None = None
    condition_level: str | None = None
    location_city: str | None = None
    draft_payload_json: dict[str, Any] | None = None


class SendMessageRequest(BaseModel):
    content_text: str = ''
    message_type: str = Field(default='text', pattern='^(text|image|video|system)$')
    asset_id: str | None = None


class ConversationReadRequest(BaseModel):
    last_read_message_id: str | None = None


class TypingIndicatorRequest(BaseModel):
    is_typing: bool = True


class ReviewCreateRequest(BaseModel):
    order_id: str
    listing_id: str | None = None
    rating: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    content: str = ''
    media_asset_ids: list[str] = Field(default_factory=list)
    anonymity_enabled: bool = False


class ReviewDraftUpdateRequest(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    tags: list[str] | None = None
    content: str | None = None
    media_asset_ids: list[str] | None = None
    anonymity_enabled: bool | None = None


class MembershipUpgradeRequest(BaseModel):
    plan_key: str


class NotificationReadRequest(BaseModel):
    read_at: str | None = None


class PageBootstrapResponse(BaseModel):
    page_key: str
    title: str | None = None
    subtitle: str | None = None
    sections: list[PageSection] = Field(default_factory=list)
    resources: dict[str, Any] = Field(default_factory=dict)


class SearchSuggestionPayload(BaseModel):
    query: str
    suggestions: list[str] = Field(default_factory=list)
    recent_queries: list[str] = Field(default_factory=list)


class SearchFacetPayload(BaseModel):
    categories: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    price_buckets: list[dict[str, Any]] = Field(default_factory=list)
    status_counts: dict[str, int] = Field(default_factory=dict)


class ReconstructionTaskResponse(BaseModel):
    task_id: str
    title: str
    description: str
    price: str
    status: str
    progress: int
    status_message: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
    video_url: str | None = None
    model_url: str | None = None
    model_ply_url: str | None = None
    model_sog_url: str | None = None
    model_format: str | None = None
    viewer_url: str | None = None
    log_url: str | None = None
    log_tail: list[str] = Field(default_factory=list)
    train_step: int | None = None
    train_total_steps: int | None = None
    train_eta: str | None = None
    train_max_steps: int | None = None
    quality_profile: str | None = None
    object_masking: bool = False
    mask_prompt_frame_url: str | None = None
    mask_prompt_frame_name: str | None = None
    mask_prompt_frame_width: int | None = None
    mask_prompt_frame_height: int | None = None
    mask_prompts_url: str | None = None
    mask_preview_url: str | None = None
    mask_preview_manifest_url: str | None = None
    mask_summary_url: str | None = None
    can_debug_masking: bool = False
    pipeline_pid: int | None = None
    mock_mode: bool = False
    is_published: bool = False
    published_at: str | None = None
    viewer_rotation_done: bool = False
    viewer_translation_done: bool = False
    viewer_initial_view_done: bool = False
    viewer_animation_approved: bool = False


class PipelineStartRequest(BaseModel):
    quality_profile: str = 'balanced'
    train_max_steps: int = 7000
    object_masking: bool = False
    mock_mode: bool | None = None


class MaskPromptPoint(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    label: int = Field(ge=0, le=1)


class MaskPromptRequest(BaseModel):
    points: list[MaskPromptPoint] = Field(default_factory=list)


class ViewerConfigUpdate(BaseModel):
    model_rotation_deg: list[float] | None = Field(default=None, min_length=3, max_length=3)
    model_translation: list[float] | None = Field(default=None, min_length=3, max_length=3)
    model_scale: float | None = None
    camera_rotation_deg: list[float] | None = Field(default=None, min_length=3, max_length=3)
    camera_distance: float | None = None


class ViewerConfigResponse(BaseModel):
    task_id: str
    viewer_config: dict[str, Any]
    task: ReconstructionTaskResponse


class PublishFlowStateUpdate(BaseModel):
    viewer_rotation_done: bool | None = None
    viewer_translation_done: bool | None = None
    viewer_initial_view_done: bool | None = None
    viewer_animation_approved: bool | None = None

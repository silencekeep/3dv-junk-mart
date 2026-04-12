from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.app.http import ok
from backend.app.schemas import (
    ConversationReadRequest,
    AuthLoginRequest,
    AuthRefreshRequest,
    AuthRegisterRequest,
    MembershipUpgradeRequest,
    NotificationReadRequest,
    ReviewCreateRequest,
    ReviewDraftUpdateRequest,
    SendMessageRequest,
    ListingDraftCreateRequest,
    ListingDraftUpdateRequest,
    LogoutRequest,
    TypingIndicatorRequest,
    UploadPresignRequest,
    UploadPresignResponse,
    UserAddressCreateRequest,
    UserAddressUpdateRequest,
    UserProfileUpdate,
)
from backend.app.services.marketplace_store import MarketplaceStore, get_store

router = APIRouter(prefix="/api/v1", tags=["marketplace"])

BASE_CURRENCY = "CNY"
DEFAULT_PAGE_SIZE = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header:
        return None
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    return token or None


def _money(amount_minor: int | None, currency: str | None = None) -> dict[str, Any]:
    return {"amount_minor": int(amount_minor or 0), "currency": currency or BASE_CURRENCY}


def _media_asset(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    asset = payload.get("asset") if isinstance(payload.get("asset"), dict) else payload
    return {
        "id": asset.get("id") or asset.get("asset_id") or asset.get("entity_id") or "",
        "kind": asset.get("kind") or "image",
        "url": asset.get("url") or asset.get("public_url") or "",
        "thumbnail_url": asset.get("thumbnail_url"),
        "width": asset.get("width"),
        "height": asset.get("height"),
        "mime_type": asset.get("mime_type"),
        "sort_order": int(asset.get("sort_order") or 0),
    }


def _current_user(store: MarketplaceStore, request: Request) -> dict[str, Any]:
    token = _bearer_token(request)
    return store.current_user(token)


def _current_user_id(store: MarketplaceStore, request: Request) -> str:
    return _current_user(store, request)["entity_id"]


def _require_current_user(store: MarketplaceStore, request: Request) -> dict[str, Any]:
    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录。")
    session = store.session_by_token(token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录。")
    user = store.user_record(session["payload"].get("user_id") or "")
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录。")
    return user


def _require_current_user_id(store: MarketplaceStore, request: Request) -> str:
    return _require_current_user(store, request)["entity_id"]


def _user_summary(store: MarketplaceStore, user_record: dict[str, Any] | None) -> dict[str, Any] | None:
    if user_record is None:
        return None
    payload = dict(user_record["payload"])
    profile = store.profile_record(user_record["entity_id"])
    profile_payload = dict(profile["payload"]) if profile else {}
    follower_count = sum(
        1
        for item in store.list_records("user_follow")
        if item["payload"].get("following_user_id") == user_record["entity_id"]
    )
    following_count = sum(
        1
        for item in store.list_records("user_follow")
        if item["payload"].get("follower_user_id") == user_record["entity_id"]
    )
    return {
        "id": user_record["entity_id"],
        "display_name": profile_payload.get("display_name") or payload.get("display_name") or "",
        "avatar_url": profile_payload.get("avatar_url") or payload.get("avatar_url"),
        "bio": profile_payload.get("bio") or payload.get("bio"),
        "location": profile_payload.get("location") or payload.get("location"),
        "sesame_credit_score": int(profile_payload.get("sesame_credit_score") or payload.get("sesame_credit_score") or 0),
        "vip_level": profile_payload.get("vip_level") or payload.get("vip_level") or "none",
        "follower_count": follower_count,
        "following_count": following_count,
        "positive_rate": profile_payload.get("positive_rate"),
    }


def _profile_detail(store: MarketplaceStore, user_record: dict[str, Any] | None) -> dict[str, Any] | None:
    if user_record is None:
        return None
    payload = dict(user_record["payload"])
    profile = store.profile_record(user_record["entity_id"])
    profile_payload = dict(profile["payload"]) if profile else {}
    birth_date = profile_payload.get("birth_date") or payload.get("birth_date")
    age_years = profile_payload.get("age_years")
    if age_years is None and birth_date:
        try:
            age_years = max(0, datetime.now().year - int(str(birth_date).split("-")[0]))
        except Exception:
            age_years = None
    return {
        "id": user_record["entity_id"],
        "display_name": profile_payload.get("display_name") or payload.get("display_name") or "",
        "avatar_url": profile_payload.get("avatar_url") or payload.get("avatar_url"),
        "birth_date": birth_date,
        "age_years": age_years,
        "bio": profile_payload.get("bio") or payload.get("bio"),
        "location": profile_payload.get("location") or payload.get("location"),
        "sesame_credit_score": int(profile_payload.get("sesame_credit_score") or payload.get("sesame_credit_score") or 0),
        "vip_level": profile_payload.get("vip_level") or payload.get("vip_level") or "none",
        "profile_visibility": profile_payload.get("profile_visibility") or payload.get("profile_visibility") or "public",
        "updated_at": profile_payload.get("updated_at") or payload.get("updated_at"),
    }


def _address_summary(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    payload = dict(record["payload"])
    return {
        "id": record["entity_id"],
        "user_id": payload.get("user_id") or "",
        "recipient_name": payload.get("recipient_name") or "",
        "phone": payload.get("phone") or "",
        "region_code": payload.get("region_code") or "",
        "address_line1": payload.get("address_line1") or "",
        "address_line2": payload.get("address_line2"),
        "is_default": bool(payload.get("is_default")),
        "created_at": payload.get("created_at") or record["created_at"],
        "updated_at": payload.get("updated_at") or record["updated_at"],
    }


def _listing_summary(store: MarketplaceStore, listing_record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(listing_record["payload"])
    seller = _user_summary(store, store.user_record(payload.get("seller_id") or ""))
    return {
        "id": listing_record["entity_id"],
        "title": payload.get("title") or "",
        "subtitle": payload.get("subtitle"),
        "price": _money(payload.get("price_minor"), payload.get("currency")),
        "original_price": _money(payload.get("original_price_minor"), payload.get("currency")) if payload.get("original_price_minor") is not None else None,
        "status": payload.get("status") or "draft",
        "cover_media": _media_asset(payload.get("cover_media_json")),
        "location": payload.get("location_city"),
        "badges": list(payload.get("badges_json") or []),
        "seller": seller,
    }


def _review_summary(store: MarketplaceStore, review_record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(review_record["payload"])
    media = [
        _media_asset(item["payload"].get("asset"))
        for item in store.list_records("review_media", parent_id=review_record["entity_id"])
    ]
    media = [item for item in media if item is not None]
    tags: list[str] = []
    for link in store.list_records("review_tag_link", parent_id=review_record["entity_id"]):
        tag_id = link["payload"].get("tag_id")
        tag = store.get_record("review_tag", tag_id) if tag_id else None
        if tag:
            tags.append(tag["payload"].get("display_name") or tag["payload"].get("tag_key") or tag_id)
    return {
        "id": review_record["entity_id"],
        "order_id": payload.get("order_id"),
        "listing_id": payload.get("listing_id"),
        "rating": int(payload.get("rating") or 0),
        "tags": tags,
        "content": payload.get("content") or "",
        "media": media,
        "anonymity_enabled": bool(payload.get("is_anonymous")),
    }


def _listing_detail(store: MarketplaceStore, listing_record: dict[str, Any]) -> dict[str, Any]:
    summary = _listing_summary(store, listing_record)
    listing_id = listing_record["entity_id"]
    payload = dict(listing_record["payload"])
    return {
        "listing": summary,
        "media": [_media_asset(item["payload"]) for item in store.list_records("listing_media", parent_id=listing_id) if _media_asset(item["payload"]) is not None],
        "seller": summary["seller"],
        "preview_3d": store.listing_preview_payload(listing_id),
        "specs": [
            {
                "spec_key": item["payload"].get("spec_key") or "",
                "spec_value": item["payload"].get("spec_value") or "",
                "sort_order": int(item["payload"].get("sort_order") or 0),
            }
            for item in store.list_records("listing_spec", parent_id=listing_id)
        ],
        "similar": [
            _listing_summary(store, item)
            for item in store.list_records("listing")
            if item["entity_id"] != listing_id and item["payload"].get("category_id") == payload.get("category_id") and item["payload"].get("status") == "live"
        ][:6],
        "inquiries": [],
        "reviews": [_review_summary(store, item) for item in store.list_records("review") if item["payload"].get("listing_id") == listing_id],
        "actions": [
            {"key": "favorite", "title": "收藏", "enabled": True},
            {"key": "chat", "title": "联系卖家", "enabled": True},
            {"key": "buy", "title": "立即购买", "enabled": summary["status"] == "live"},
        ],
        "listing_payload": payload,
    }


def _conversation_summary(store: MarketplaceStore, conversation_record: dict[str, Any], *, current_user_id: str | None = None) -> dict[str, Any]:
    payload = dict(conversation_record["payload"])
    buyer = store.user_record(payload.get("buyer_id") or "")
    seller = store.user_record(payload.get("seller_id") or "")
    if current_user_id and current_user_id == payload.get("buyer_id"):
        other = seller
    elif current_user_id and current_user_id == payload.get("seller_id"):
        other = buyer
    else:
        other = seller or buyer
    return {
        "id": conversation_record["entity_id"],
        "listing_id": payload.get("listing_id"),
        "other_user": _user_summary(store, other),
        "last_message_preview": payload.get("last_message_preview"),
        "unread_count": int(payload.get("unread_count") or 0),
        "updated_at": payload.get("updated_at"),
    }


def _conversation_detail(store: MarketplaceStore, conversation_record: dict[str, Any], *, current_user_id: str | None = None) -> dict[str, Any]:
    payload = dict(conversation_record["payload"])
    conversation_id = conversation_record["entity_id"]
    messages = sorted(
        store.list_records("message", parent_id=conversation_id),
        key=lambda item: item["payload"].get("created_at") or "",
    )
    listing = store.get_record("listing", payload.get("listing_id") or "")
    return {
        "conversation": _conversation_summary(store, conversation_record, current_user_id=current_user_id),
        "item_preview": _listing_summary(store, listing) if listing else None,
        "safety_banner": {
            "title": "平台安全提醒",
            "body": "请勿在站外转账，交易与售后尽量保留在平台内完成。",
            "level": "info",
        },
        "messages": [
            {
                "id": item["entity_id"],
                "conversation_id": conversation_id,
                "sender_id": item["payload"].get("sender_id"),
                "message_type": item["payload"].get("message_type") or "text",
                "content_text": item["payload"].get("content_text") or "",
                "asset": _media_asset(item["payload"].get("asset")),
                "created_at": item["payload"].get("created_at"),
                "read_at": item["payload"].get("read_at"),
            }
            for item in messages
        ],
        "composer": {
            "placeholder": "发送消息",
            "allowed_message_types": ["text", "image", "video", "system"],
            "quick_actions": ["发送图片", "发送视频", "查看订单"],
        },
    }


def _order_summary(store: MarketplaceStore, order_record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(order_record["payload"])
    item_snapshot = dict(payload.get("item_snapshot_json") or {})
    logistics = dict(payload.get("logistics_json") or {})
    return {
        "id": order_record["entity_id"],
        "status": payload.get("status") or "pending",
        "buyer": _user_summary(store, store.user_record(payload.get("buyer_id") or "")),
        "seller": _user_summary(store, store.user_record(payload.get("seller_id") or "")),
        "item_snapshot": item_snapshot,
        "totals": {
            "subtotal": _money(payload.get("subtotal_minor"), payload.get("currency")),
            "shipping": _money(payload.get("shipping_minor"), payload.get("currency")),
            "discount": _money(payload.get("discount_minor"), payload.get("currency")),
            "total": _money(payload.get("total_minor"), payload.get("currency")),
        },
        "logistics": logistics,
        "can_confirm_receipt": bool(payload.get("can_confirm_receipt")),
    }


def _order_detail(store: MarketplaceStore, order_record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(order_record["payload"])
    order_id = order_record["entity_id"]
    timeline = sorted(
        store.list_records("order_event", parent_id=order_id),
        key=lambda item: item["payload"].get("occurred_at") or "",
    )
    shipment = store.find_first("shipment", predicate=lambda item: item["payload"].get("order_id") == order_id)
    shipment_events = []
    if shipment is not None:
        shipment_events = [
            {
                "id": item["entity_id"],
                "shipment_id": item["payload"].get("shipment_id"),
                "event_code": item["payload"].get("event_code") or "",
                "event_text": item["payload"].get("event_text") or "",
                "event_city": item["payload"].get("event_city"),
                "occurred_at": item["payload"].get("occurred_at"),
            }
            for item in store.list_records("shipment_event", parent_id=shipment["entity_id"])
        ]
    return {
        "order": _order_summary(store, order_record),
        "timeline": [
            {
                "id": item["entity_id"],
                "order_id": order_id,
                "status": item["payload"].get("status") or "",
                "event_note": item["payload"].get("event_note") or "",
                "actor_user_id": item["payload"].get("actor_user_id"),
                "occurred_at": item["payload"].get("occurred_at"),
            }
            for item in timeline
        ],
        "receipt": {
            "payment": {
                "id": f"payment_{order_id}",
                "order_id": order_id,
                "payment_method": payload.get("payment_method") or "wechat_pay",
                "status": payload.get("payment_status") or "paid",
                "amount": _money(payload.get("total_minor"), payload.get("currency")),
                "provider_ref": payload.get("provider_ref"),
            },
            "shipment": {
                "id": shipment["entity_id"] if shipment else None,
                "order_id": order_id,
                "carrier_name": shipment["payload"].get("carrier_name") if shipment else None,
                "tracking_no": shipment["payload"].get("tracking_no") if shipment else None,
                "status": shipment["payload"].get("status") if shipment else None,
                "shipped_at": shipment["payload"].get("shipped_at") if shipment else None,
                "estimated_delivery_at": shipment["payload"].get("estimated_delivery_at") if shipment else None,
                "events": shipment_events,
            },
        },
        "action_bar": [
            {"key": "contact_seller", "title": "联系卖家", "enabled": True},
            {"key": "track_shipment", "title": "查看物流", "enabled": shipment is not None},
            {"key": "confirm_receipt", "title": "确认收货", "enabled": bool(payload.get("can_confirm_receipt"))},
        ],
    }


def _notification_summary(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record["payload"])
    return {
        "id": record["entity_id"],
        "user_id": payload.get("user_id"),
        "notification_type": payload.get("notification_type") or "system",
        "title": payload.get("title") or "",
        "body": payload.get("body") or "",
        "entity_type": payload.get("entity_type"),
        "entity_id": payload.get("entity_id"),
        "read_at": payload.get("read_at"),
        "created_at": payload.get("created_at"),
    }


def _wallet_summary(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record["payload"])
    return {
        "available_minor": int(payload.get("available_minor") or 0),
        "held_minor": int(payload.get("held_minor") or 0),
        "currency": payload.get("currency") or BASE_CURRENCY,
        "status": payload.get("status") or "active",
    }


def _page(page_key: str, *, title: str | None = None, subtitle: str | None = None, sections: list[dict[str, Any]] | None = None, resources: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "page_key": page_key,
        "title": title,
        "subtitle": subtitle,
        "sections": sections or [],
        "resources": resources or {},
    }


def _listings_by_status(store: MarketplaceStore, status_name: str | None = None) -> list[dict[str, Any]]:
    items = store.list_records("listing")
    if status_name:
        items = [item for item in items if item["payload"].get("status") == status_name]
    return items


@router.get("/health")
def health(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    return ok(request, store.health_snapshot())


@router.get("/version")
def version(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    return ok(request, store.version_snapshot())


@router.get("/config/public")
def public_config(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    return ok(request, store.public_config_snapshot())


@router.get("/pages/auth/login")
def page_auth_login(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    return ok(request, _page(
        "auth_login",
        title="欢迎登录",
        subtitle="登录后即可管理你的商品、订单和消息。",
        sections=[
            {
                "section_type": "form",
                "section_id": "login_form",
                "title": "登录",
                "items": [
                    {"field": "identifier", "label": "账号"},
                    {"field": "password", "label": "密码"},
                ],
                "actions": [
                    {"key": "login", "title": "登录"},
                    {"key": "guest", "title": "游客进入", "enabled": True},
                ],
            }
        ],
        resources={"public_config": store.public_config_snapshot()},
    ))


@router.get("/pages/auth/register")
def page_auth_register(request: Request) -> dict[str, Any]:
    return ok(request, _page(
        "auth_register",
        title="创建账号",
        subtitle="注册后即可发布商品、查看订单与聊天记录。",
        sections=[
            {
                "section_type": "form",
                "section_id": "register_form",
                "title": "注册",
                "items": [
                    {"field": "display_name", "label": "昵称"},
                    {"field": "identifier", "label": "账号"},
                    {"field": "password", "label": "密码"},
                    {"field": "consent_version", "label": "同意版本"},
                ],
                "actions": [{"key": "register", "title": "注册"}],
            }
        ],
    ))


@router.get("/pages/me/settings")
def page_me_settings(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    addresses = [item for item in (_address_summary(record) for record in store.list_user_addresses(user["entity_id"])) if item is not None]
    default_address = _address_summary(store.default_user_address(user["entity_id"]))
    return ok(request, _page(
        "me_settings",
        title="个人资料设置",
        subtitle="管理头像、昵称、生日和隐私可见性。",
        sections=[
            {
                "section_type": "form",
                "section_id": "profile_settings",
                "title": "资料编辑",
                "items": [
                    {"field": "avatar_url", "label": "头像"},
                    {"field": "display_name", "label": "昵称"},
                    {"field": "birth_date", "label": "生日"},
                    {"field": "bio", "label": "简介"},
                    {"field": "location", "label": "所在地"},
                    {"field": "profile_visibility", "label": "可见性"},
                ],
                "actions": [{"key": "save", "title": "保存"}],
            },
            {
                "section_type": "list",
                "section_id": "shipping_addresses",
                "title": "收货地址",
                "items": addresses,
                "actions": [{"key": "add_address", "title": "新增地址"}],
            }
        ],
        resources={"profile": _profile_detail(store, user), "addresses": addresses, "default_address": default_address},
    ))


@router.post("/auth/register")
def auth_register(request: Request, payload: AuthRegisterRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    if store.user_by_identifier(payload.identifier) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该账号已存在。")

    now = _now()
    user_id = _new_id("user")
    password_hash = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()
    user_record = {
        "id": user_id,
        "identifier": payload.identifier.strip(),
        "password_hash": password_hash,
        "display_name": payload.display_name.strip(),
        "avatar_url": None,
        "bio": None,
        "location": None,
        "sesame_credit_score": 600,
        "vip_level": "none",
        "profile_visibility": "public",
        "birth_date": None,
        "status": "active",
        "registered_at": now,
        "last_login_at": now,
        "password_updated_at": now,
        "account_locked_until": None,
        "created_at": now,
        "updated_at": now,
    }
    store.upsert_record("user", user_id, user_record)
    store.upsert_record(
        "user_profile",
        user_id,
        {
            "id": user_id,
            "display_name": payload.display_name.strip(),
            "avatar_url": None,
            "birth_date": None,
            "age_years": None,
            "bio": None,
            "location": None,
            "sesame_credit_score": 600,
            "vip_level": "none",
            "profile_visibility": "public",
            "updated_at": now,
        },
    )
    store.upsert_record(
        "user_consent",
        consent_id := _new_id("consent"),
        {
            "id": consent_id,
            "user_id": user_id,
            "consent_type": "terms_and_privacy",
            "consent_version": payload.consent_version,
            "accepted_at": now,
            "metadata_json": {"source": "register"},
        },
        parent_id=user_id,
    )
    session = store.create_session(user_id, device_name=payload.device_name, device_platform=payload.device_platform, is_new_user=True)
    store.upsert_record(
        "login_attempt",
        _new_id("attempt"),
        {
            "id": _new_id("attempt"),
            "login_identifier": payload.identifier,
            "user_id": user_id,
            "success": True,
            "failure_reason": None,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "occurred_at": now,
        },
    )
    user_record = store.user_record(user_id)
    return ok(request, {"user": _user_summary(store, user_record), "session": session, "profile": _profile_detail(store, user_record)})


@router.post("/auth/login")
def auth_login(request: Request, payload: AuthLoginRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_record = store.user_by_identifier(payload.identifier)
    now = _now()
    if user_record is None or not store.verify_password(user_record, payload.password):
        store.upsert_record(
            "login_attempt",
            _new_id("attempt"),
            {
                "id": _new_id("attempt"),
                "login_identifier": payload.identifier,
                "user_id": user_record["entity_id"] if user_record else None,
                "success": False,
                "failure_reason": "invalid_credentials",
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "occurred_at": now,
            },
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码不正确。")

    user_payload = dict(user_record["payload"])
    user_payload["last_login_at"] = now
    user_payload["updated_at"] = now
    store.upsert_record("user", user_record["entity_id"], user_payload)
    session = store.create_session(user_record["entity_id"], device_name=payload.device_name, device_platform=payload.device_platform, is_new_user=False)
    store.upsert_record(
        "login_attempt",
        _new_id("attempt"),
        {
            "id": _new_id("attempt"),
            "login_identifier": payload.identifier,
            "user_id": user_record["entity_id"],
            "success": True,
            "failure_reason": None,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "occurred_at": now,
        },
    )
    return ok(request, {"user": _user_summary(store, user_record), "session": session, "profile": _profile_detail(store, user_record)})


@router.post("/auth/refresh")
def auth_refresh(request: Request, payload: AuthRefreshRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    session_record = store.find_first("auth_session", predicate=lambda item: item["payload"].get("refresh_token") == payload.refresh_token)
    if session_record is None or session_record["payload"].get("revoked_at"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已失效。")
    user_record = store.user_record(session_record["payload"]["user_id"])
    if user_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")
    store.revoke_session(session_record["payload"].get("access_token"))
    session = store.create_session(user_record["entity_id"], device_name=session_record["payload"].get("device_name"), device_platform=session_record["payload"].get("device_platform"), is_new_user=False)
    return ok(request, {"user": _user_summary(store, user_record), "session": session, "profile": _profile_detail(store, user_record)})


@router.post("/auth/logout")
def auth_logout(request: Request, payload: LogoutRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    token = payload.access_token or _bearer_token(request)
    session = store.revoke_session(token)
    return ok(request, {"revoked": session is not None})


@router.get("/auth/session")
def auth_session(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    token = _bearer_token(request)
    session = store.session_by_token(token)
    if session is None:
        session = store.session_by_token("demo-access-token")
    user_id = session["payload"]["user_id"] if session else store.default_user_id()
    user_record = store.user_record(user_id)
    return ok(request, {"user": _user_summary(store, user_record), "session": session["payload"] if session else None, "profile": _profile_detail(store, user_record)})


@router.get("/users/me")
def users_me(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    return ok(request, _profile_detail(store, user))


@router.patch("/users/me")
def users_me_patch(request: Request, payload: UserProfileUpdate, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    profile = store.update_user_profile(user["entity_id"], payload.model_dump(exclude_none=True))
    return ok(request, profile["payload"])


@router.get("/users/me/stats")
def users_me_stats(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    return ok(request, store.user_stats_payload(user["entity_id"]))


@router.get("/users/me/listings")
def users_me_listings(request: Request, store: MarketplaceStore = Depends(get_store), page: int = Query(1, ge=1), page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    items = [_listing_summary(store, item) for item in store.list_records("listing") if item["payload"].get("seller_id") == user_id]
    page_items, page_meta = store.paginate(items, page=page, page_size=page_size)
    return ok(request, page_items, page=page_meta)


@router.get("/users/me/favorites")
def users_me_favorites(request: Request, store: MarketplaceStore = Depends(get_store), page: int = Query(1, ge=1), page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    favorite_ids = {item["payload"].get("listing_id") for item in store.list_records("listing_favorite") if item["payload"].get("user_id") == user_id}
    items = [_listing_summary(store, item) for item in store.list_records("listing") if item["entity_id"] in favorite_ids]
    page_items, page_meta = store.paginate(items, page=page, page_size=page_size)
    return ok(request, page_items, page=page_meta)


@router.get("/users/me/addresses")
def users_me_addresses(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    items = [item for item in (_address_summary(record) for record in store.list_user_addresses(user["entity_id"])) if item is not None]
    return ok(request, items)


@router.post("/users/me/addresses")
def users_me_address_create(request: Request, payload: UserAddressCreateRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    address = store.create_user_address(user["entity_id"], payload.model_dump(exclude_none=True))
    return ok(request, _address_summary(address))


@router.get("/users/me/addresses/{address_id}")
def users_me_address_detail(request: Request, address_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    address = store.get_user_address(address_id)
    if address is None or address["payload"].get("user_id") != user["entity_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在。")
    return ok(request, _address_summary(address))


@router.patch("/users/me/addresses/{address_id}")
def users_me_address_update(request: Request, address_id: str, payload: UserAddressUpdateRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    address = store.get_user_address(address_id)
    if address is None or address["payload"].get("user_id") != user["entity_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在。")
    updated = store.update_user_address(address_id, payload.model_dump(exclude_none=True))
    return ok(request, _address_summary(updated))


@router.delete("/users/me/addresses/{address_id}")
def users_me_address_delete(request: Request, address_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    address = store.get_user_address(address_id)
    if address is None or address["payload"].get("user_id") != user["entity_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在。")
    store.delete_user_address(address_id)
    return ok(request, {"address_id": address_id, "deleted": True})


@router.get("/users/{user_id}")
def users_detail(user_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = store.user_record(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")
    return ok(None, _profile_detail(store, user))


@router.get("/users/{user_id}/followers")
def users_followers(user_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    followers = [_user_summary(store, store.user_record(item["payload"].get("follower_user_id") or "")) for item in store.list_records("user_follow") if item["payload"].get("following_user_id") == user_id]
    return ok(None, [item for item in followers if item is not None])


@router.get("/users/{user_id}/following")
def users_following(user_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    following = [_user_summary(store, store.user_record(item["payload"].get("following_user_id") or "")) for item in store.list_records("user_follow") if item["payload"].get("follower_user_id") == user_id]
    return ok(None, [item for item in following if item is not None])


@router.get("/pages/me")
def page_me(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    profile = _profile_detail(store, user)
    listings = [_listing_summary(store, item) for item in store.list_records("listing") if item["payload"].get("seller_id") == user["entity_id"]]
    addresses = [item for item in (_address_summary(record) for record in store.list_user_addresses(user["entity_id"])) if item is not None]
    stats = store.user_stats_payload(user["entity_id"])
    return ok(request, _page(
        "me",
        title="我的",
        subtitle="查看个人资料、统计、收藏和快捷入口。",
        sections=[
            {"section_type": "profile", "section_id": "profile_card", "items": [profile]},
            {"section_type": "grid", "section_id": "services", "items": [item["payload"] for item in store.list_records("service_card")]},
            {"section_type": "list", "section_id": "my_listings", "title": "我发布的商品", "items": listings},
            {"section_type": "list", "section_id": "my_addresses", "title": "收货地址", "items": addresses},
        ],
        resources={"profile": profile, "stats": stats, "listings": listings, "addresses": addresses, "badge_summary": store.badge_summary_payload(user["entity_id"])},
    ))


@router.get("/categories")
def categories(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    items = [item["payload"] for item in store.list_records("category")]
    items.sort(key=lambda item: item.get("sort_order", 0))
    return ok(request, items)


@router.get("/service-catalog")
def service_catalog(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    items = [item["payload"] for item in store.list_records("service_card")]
    items.sort(key=lambda item: item.get("sort_order", 0))
    return ok(request, items)


@router.get("/banners")
def banners(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    items = [item["payload"] for item in store.list_records("banner") if item["payload"].get("active", True)]
    items.sort(key=lambda item: item.get("sort_order", 0))
    return ok(request, items)


@router.get("/pages/home")
def page_home(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    listings = [_listing_summary(store, item) for item in _listings_by_status(store, "live")]
    sections = [
        {"section_type": "hero", "section_id": "home_hero", "title": "3D 闲置好物", "subtitle": "从二手商品到 3D 展示，一站式体验。", "items": [item["payload"] for item in store.list_records("banner") if item["payload"].get("active", True)]},
        {"section_type": "grid", "section_id": "home_categories", "title": "分类浏览", "items": [item["payload"] for item in store.list_records("category")]},
        {"section_type": "list", "section_id": "home_recommendations", "title": "推荐商品", "items": listings[:6]},
        {"section_type": "grid", "section_id": "home_services", "title": "快捷入口", "items": [item["payload"] for item in store.list_records("service_card")]},
    ]
    return ok(request, _page("home", title="首页", sections=sections, resources={"listings": listings[:10]}))


@router.get("/pages/search")
def page_search(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    documents = store.search_documents()
    return ok(request, _page(
        "search",
        title="搜索",
        subtitle="按分类、价格和地点筛选商品。",
        sections=[
            {"section_type": "notice", "section_id": "search_notice", "title": "搜索建议", "items": ["输入关键词即可快速找到商品"]},
            {"section_type": "list", "section_id": "search_hot", "title": "热搜", "items": [item["payload"] for item in store.list_records("search_suggestion")]},
        ],
        resources={"documents": documents},
    ))


@router.get("/search/suggestions")
def search_suggestions(request: Request, query: str = Query(""), store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    record = store.find_first("search_suggestion")
    suggestions = list(record["payload"].get("suggestions") or []) if record else []
    recent = list(record["payload"].get("recent_queries") or []) if record else []
    if query:
        lowered = query.lower()
        suggestions = [item for item in suggestions if lowered in item.lower() or item.startswith(query)] or suggestions
    return ok(request, {"query": query, "suggestions": suggestions, "recent_queries": recent})


@router.get("/search/facets")
def search_facets(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    listings = [_listing_summary(store, item) for item in store.list_records("listing")]
    category_counts: dict[str, int] = {}
    location_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    prices = [listing["price"]["amount_minor"] for listing in listings]
    for listing in listings:
        record = store.get_record("listing", listing["id"])
        category_id = record["payload"].get("category_id") if record else None
        if category_id:
            category_counts[category_id] = category_counts.get(category_id, 0) + 1
        status_counts[listing["status"]] = status_counts.get(listing["status"], 0) + 1
        if listing.get("location"):
            location_counts[listing["location"]] = location_counts.get(listing["location"], 0) + 1
    categories = []
    for item in store.list_records("category"):
        categories.append({"id": item["entity_id"], "name": item["payload"].get("name"), "count": category_counts.get(item["entity_id"], 0)})
    facets = {
        "categories": categories,
        "locations": [{"id": name, "name": name, "count": count} for name, count in location_counts.items()],
        "price_buckets": [
            {"id": "lt_1000", "label": "1000 元以下", "count": sum(1 for price in prices if price < 100000)},
            {"id": "1000_5000", "label": "1000-5000 元", "count": sum(1 for price in prices if 100000 <= price < 500000)},
            {"id": "gte_5000", "label": "5000 元以上", "count": sum(1 for price in prices if price >= 500000)},
        ],
        "status_counts": status_counts,
    }
    return ok(request, facets)


@router.get("/listings")
def listings(
    request: Request,
    store: MarketplaceStore = Depends(get_store),
    query: str = Query(""),
    status_name: str | None = Query(None, alias="status"),
    category_id: str | None = None,
    seller_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> dict[str, Any]:
    items = [_listing_summary(store, item) for item in store.list_records("listing")]
    if query:
        lowered = query.lower()
        items = [item for item in items if lowered in item["title"].lower() or lowered in (item.get("subtitle") or "").lower()]
    if status_name:
        items = [item for item in items if item["status"] == status_name]
    if category_id:
        items = [item for item in items if (store.get_record("listing", item["id"]) or {"payload": {}})["payload"].get("category_id") == category_id]
    if seller_id:
        items = [item for item in items if item["seller"] and item["seller"]["id"] == seller_id]
    page_items, page_meta = store.paginate(items, page=page, page_size=page_size)
    return ok(request, page_items, page=page_meta)


@router.get("/categories/{category_id}/listings")
def category_listings(request: Request, category_id: str, store: MarketplaceStore = Depends(get_store), page: int = Query(1, ge=1), page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100)) -> dict[str, Any]:
    items = [_listing_summary(store, item) for item in store.list_records("listing") if item["payload"].get("category_id") == category_id]
    page_items, page_meta = store.paginate(items, page=page, page_size=page_size)
    return ok(request, page_items, page=page_meta)


@router.get("/pages/listings/{listing_id}")
def page_listing(request: Request, listing_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    listing = store.get_record("listing", listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在。")
    return ok(request, _page("listing_detail", title="商品详情", resources=_listing_detail(store, listing)))


@router.get("/listings/{listing_id}")
def listing_detail(request: Request, listing_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    listing = store.get_record("listing", listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在。")
    return ok(request, _listing_detail(store, listing))


@router.get("/listings/{listing_id}/media")
def listing_media(request: Request, listing_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    items = [_media_asset(item["payload"]) for item in store.list_records("listing_media", parent_id=listing_id)]
    return ok(request, [item for item in items if item is not None])


@router.get("/listings/{listing_id}/seller")
def listing_seller(request: Request, listing_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    listing = store.get_record("listing", listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在。")
    seller = _user_summary(store, store.user_record(listing["payload"].get("seller_id") or ""))
    return ok(request, seller)


@router.get("/listings/{listing_id}/specs")
def listing_specs(request: Request, listing_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    items = [
        {"spec_key": item["payload"].get("spec_key"), "spec_value": item["payload"].get("spec_value"), "sort_order": item["payload"].get("sort_order")}
        for item in store.list_records("listing_spec", parent_id=listing_id)
    ]
    return ok(request, items)


@router.get("/listings/{listing_id}/similar")
def listing_similar(request: Request, listing_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    listing = store.get_record("listing", listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在。")
    category_id = listing["payload"].get("category_id")
    items = [_listing_summary(store, item) for item in store.list_records("listing") if item["entity_id"] != listing_id and item["payload"].get("category_id") == category_id]
    return ok(request, items[:6])


@router.get("/listings/{listing_id}/inquiries")
def listing_inquiries(request: Request, listing_id: str) -> dict[str, Any]:
    return ok(request, [])


@router.post("/listings/{listing_id}/favorite")
def favorite_listing(request: Request, listing_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    favorite_id = f"favorite_{user_id}_{listing_id}"
    if store.get_record("listing_favorite", favorite_id) is None:
        store.upsert_record("listing_favorite", favorite_id, {"user_id": user_id, "listing_id": listing_id, "created_at": _now()}, parent_id=listing_id)
    return ok(request, {"listing_id": listing_id, "favorite": True})


@router.delete("/listings/{listing_id}/favorite")
def unfavorite_listing(request: Request, listing_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    store.delete_record("listing_favorite", f"favorite_{user_id}_{listing_id}")
    return ok(request, {"listing_id": listing_id, "favorite": False})


@router.post("/listings/drafts")
def create_listing_draft(request: Request, payload: ListingDraftCreateRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    draft_id = _new_id("draft")
    record = {
        "id": draft_id,
        "seller_id": user_id,
        "category_id": payload.category_id,
        "title": payload.title,
        "subtitle": payload.subtitle,
        "description": payload.description,
        "price_minor": payload.price_minor,
        "original_price_minor": payload.original_price_minor,
        "currency": payload.currency,
        "status": "draft",
        "condition_level": payload.condition_level,
        "location_city": payload.location_city,
        "draft_payload_json": payload.draft_payload_json,
        "created_at": _now(),
        "updated_at": _now(),
    }
    store.upsert_record("listing_draft", draft_id, record, parent_id=user_id)
    return ok(request, record)


@router.get("/listings/drafts/{draft_id}")
def get_listing_draft(request: Request, draft_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    draft = store.get_record("listing_draft", draft_id)
    if draft is None or draft["payload"].get("seller_id") != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="草稿不存在。")
    return ok(request, draft["payload"])


@router.patch("/listings/drafts/{draft_id}")
def update_listing_draft(request: Request, draft_id: str, payload: ListingDraftUpdateRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    draft = store.get_record("listing_draft", draft_id)
    if draft is None or draft["payload"].get("seller_id") != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="草稿不存在。")
    changes = payload.model_dump(exclude_none=True)
    updated = dict(draft["payload"])
    updated.update(changes)
    updated["updated_at"] = _now()
    store.upsert_record("listing_draft", draft_id, updated, parent_id=updated.get("seller_id"))
    return ok(request, updated)


@router.post("/listings/drafts/{draft_id}/publish")
def publish_listing_draft(request: Request, draft_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    draft = store.get_record("listing_draft", draft_id)
    if draft is None or draft["payload"].get("seller_id") != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="草稿不存在。")
    draft_payload = dict(draft["payload"])
    listing_id = draft_payload.get("listing_id") or _new_id("listing")
    listing_payload = {
        "id": listing_id,
        "seller_id": draft_payload.get("seller_id"),
        "category_id": draft_payload.get("category_id"),
        "title": draft_payload.get("title") or "",
        "subtitle": draft_payload.get("subtitle"),
        "description": draft_payload.get("description") or "",
        "price_minor": draft_payload.get("price_minor") or 0,
        "original_price_minor": draft_payload.get("original_price_minor"),
        "currency": draft_payload.get("currency") or BASE_CURRENCY,
        "status": "live",
        "condition_level": draft_payload.get("condition_level"),
        "location_city": draft_payload.get("location_city"),
        "cover_media_json": draft_payload.get("cover_media_json"),
        "badges_json": draft_payload.get("badges_json") or [],
        "model_url": draft_payload.get("model_url"),
        "model_ply_url": draft_payload.get("model_ply_url"),
        "model_sog_url": draft_payload.get("model_sog_url"),
        "model_format": draft_payload.get("model_format"),
        "viewer_url": draft_payload.get("viewer_url"),
        "log_url": draft_payload.get("log_url"),
        "remote_task_id": draft_payload.get("remote_task_id"),
        "object_masking": bool(draft_payload.get("object_masking", False)),
        "quality_profile": draft_payload.get("quality_profile"),
        "published_at": _now(),
        "created_at": draft_payload.get("created_at") or _now(),
        "updated_at": _now(),
    }
    store.upsert_record("listing", listing_id, listing_payload)
    return ok(request, _listing_summary(store, store.get_record("listing", listing_id)))


@router.post("/uploads/presign")
def upload_presign(request: Request, payload: UploadPresignRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    _require_current_user_id(store, request)
    filename = payload.filename or "upload.bin"
    kind = payload.kind or "image"
    asset_id = _new_id("asset")
    relative_url = f"/storage/uploads/{asset_id}/{filename}"
    response = UploadPresignResponse(
        asset_id=asset_id,
        upload_url=relative_url,
        public_url=relative_url,
        expires_at=_now(),
        kind=kind,
    )
    return ok(request, response.model_dump(mode="json"))


@router.get("/conversations")
def conversations(
    request: Request,
    store: MarketplaceStore = Depends(get_store),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    items = []
    for record in store.list_records("conversation"):
        payload = record["payload"]
        if user_id not in {payload.get("buyer_id"), payload.get("seller_id")}:
            continue
        items.append(_conversation_summary(store, record, current_user_id=user_id))
    page_items, page_meta = store.paginate(items, page=page, page_size=page_size)
    return ok(request, page_items, page=page_meta)


@router.get("/conversations/{conversation_id}")
def conversation_detail(request: Request, conversation_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    conversation = store.get_record("conversation", conversation_id)
    if conversation is None or user["entity_id"] not in {conversation["payload"].get("buyer_id"), conversation["payload"].get("seller_id")}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")
    return ok(request, _conversation_detail(store, conversation, current_user_id=user["entity_id"]))


@router.post("/conversations/{conversation_id}/messages")
def send_conversation_message(
    request: Request,
    conversation_id: str,
    payload: SendMessageRequest,
    store: MarketplaceStore = Depends(get_store),
) -> dict[str, Any]:
    user = _require_current_user(store, request)
    conversation = store.get_record("conversation", conversation_id)
    if conversation is None or user["entity_id"] not in {conversation["payload"].get("buyer_id"), conversation["payload"].get("seller_id")}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")
    now = _now()
    asset = None
    if payload.asset_id:
        asset = {
            "id": payload.asset_id,
            "kind": payload.message_type if payload.message_type in {"image", "video"} else "image",
            "url": f"/storage/uploads/{payload.asset_id}",
            "thumbnail_url": None,
            "width": None,
            "height": None,
            "mime_type": None,
            "sort_order": 0,
        }
    message_id = _new_id("message")
    message_payload = {
        "id": message_id,
        "conversation_id": conversation_id,
        "sender_id": user["entity_id"],
        "message_type": payload.message_type,
        "content_text": payload.content_text,
        "asset": asset,
        "created_at": now,
        "read_at": None,
    }
    store.upsert_record("message", message_id, message_payload, parent_id=conversation_id)
    conversation_payload = dict(conversation["payload"])
    conversation_payload["last_message_preview"] = payload.content_text or ("发送了图片" if asset else "新消息")
    conversation_payload["updated_at"] = now
    conversation_payload["unread_count"] = int(conversation_payload.get("unread_count") or 0) + 1
    store.upsert_record("conversation", conversation_id, conversation_payload)
    return ok(request, message_payload)


@router.post("/conversations/{conversation_id}/read")
def read_conversation(
    request: Request,
    conversation_id: str,
    payload: ConversationReadRequest,
    store: MarketplaceStore = Depends(get_store),
) -> dict[str, Any]:
    user = _require_current_user(store, request)
    conversation = store.get_record("conversation", conversation_id)
    if conversation is None or user["entity_id"] not in {conversation["payload"].get("buyer_id"), conversation["payload"].get("seller_id")}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")
    user_id = user["entity_id"]
    member = store.find_first(
        "conversation_member",
        predicate=lambda item: item["payload"].get("conversation_id") == conversation_id and item["payload"].get("user_id") == user_id,
    )
    if member is not None:
        member_payload = dict(member["payload"])
        member_payload["last_read_message_id"] = payload.last_read_message_id
        member_payload["unread_count"] = 0
        store.upsert_record("conversation_member", member["entity_id"], member_payload, parent_id=conversation_id)
    conversation_payload = dict(conversation["payload"])
    conversation_payload["unread_count"] = 0
    store.upsert_record("conversation", conversation_id, conversation_payload)
    return ok(request, {"conversation_id": conversation_id, "last_read_message_id": payload.last_read_message_id, "read_at": _now()})


@router.post("/conversations/{conversation_id}/typing")
def conversation_typing(
    request: Request,
    conversation_id: str,
    payload: TypingIndicatorRequest,
    store: MarketplaceStore = Depends(get_store),
) -> dict[str, Any]:
    _require_current_user_id(store, request)
    return ok(request, {"conversation_id": conversation_id, "is_typing": payload.is_typing})


@router.get("/orders")
def orders(
    request: Request,
    store: MarketplaceStore = Depends(get_store),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    items = []
    for record in store.list_records("order"):
        payload = record["payload"]
        if user_id not in {payload.get("buyer_id"), payload.get("seller_id")}:
            continue
        items.append(_order_summary(store, record))
    page_items, page_meta = store.paginate(items, page=page, page_size=page_size)
    return ok(request, page_items, page=page_meta)


@router.get("/orders/{order_id}")
def order_detail(request: Request, order_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    order = store.get_record("order", order_id)
    if order is None or user["entity_id"] not in {order["payload"].get("buyer_id"), order["payload"].get("seller_id")}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在。")
    return ok(request, _order_detail(store, order))


@router.get("/orders/{order_id}/timeline")
def order_timeline(request: Request, order_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    order = store.get_record("order", order_id)
    if order is None or user["entity_id"] not in {order["payload"].get("buyer_id"), order["payload"].get("seller_id")}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在。")
    return ok(request, _order_detail(store, order)["timeline"])


@router.get("/orders/{order_id}/shipment")
def order_shipment(request: Request, order_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    order = store.get_record("order", order_id)
    if order is None or user["entity_id"] not in {order["payload"].get("buyer_id"), order["payload"].get("seller_id")}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在。")
    return ok(request, _order_detail(store, order)["receipt"]["shipment"])


@router.post("/orders/{order_id}/confirm-receipt")
def confirm_receipt(request: Request, order_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    order = store.get_record("order", order_id)
    if order is None or user["entity_id"] not in {order["payload"].get("buyer_id"), order["payload"].get("seller_id")}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在。")
    payload = dict(order["payload"])
    payload["status"] = "completed"
    payload["shipping_status"] = "delivered"
    payload["can_confirm_receipt"] = False
    payload["updated_at"] = _now()
    store.upsert_record("order", order_id, payload)
    store.upsert_record(
        "order_event",
        _new_id("order_event"),
        {
            "id": _new_id("order_event"),
            "order_id": order_id,
            "status": "completed",
            "event_note": "买家已确认收货",
            "actor_user_id": user["entity_id"],
            "occurred_at": _now(),
        },
        parent_id=order_id,
    )
    return ok(request, _order_detail(store, store.get_record("order", order_id) or order))


@router.post("/orders/{order_id}/cancel")
def cancel_order(request: Request, order_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    order = store.get_record("order", order_id)
    if order is None or user["entity_id"] not in {order["payload"].get("buyer_id"), order["payload"].get("seller_id")}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在。")
    payload = dict(order["payload"])
    payload["status"] = "cancelled"
    payload["payment_status"] = "refunded"
    payload["updated_at"] = _now()
    store.upsert_record("order", order_id, payload)
    store.upsert_record(
        "order_event",
        _new_id("order_event"),
        {
            "id": _new_id("order_event"),
            "order_id": order_id,
            "status": "cancelled",
            "event_note": "订单已取消",
            "actor_user_id": user["entity_id"],
            "occurred_at": _now(),
        },
        parent_id=order_id,
    )
    return ok(request, _order_detail(store, store.get_record("order", order_id) or order))


@router.get("/reviews")
def reviews(
    request: Request,
    store: MarketplaceStore = Depends(get_store),
    listing_id: str | None = None,
    order_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> dict[str, Any]:
    items = []
    for record in store.list_records("review"):
        payload = record["payload"]
        if listing_id and payload.get("listing_id") != listing_id:
            continue
        if order_id and payload.get("order_id") != order_id:
            continue
        items.append(_review_summary(store, record))
    page_items, page_meta = store.paginate(items, page=page, page_size=page_size)
    return ok(request, page_items, page=page_meta)


@router.post("/reviews")
def create_review(request: Request, payload: ReviewCreateRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    review_id = _new_id("review")
    now = _now()
    user = _require_current_user(store, request)
    order = store.get_record("order", payload.order_id)
    seller_user_id = None
    if order is not None:
        seller_user_id = order["payload"].get("seller_id")
    elif payload.listing_id:
        listing = store.get_record("listing", payload.listing_id)
        seller_user_id = listing["payload"].get("seller_id") if listing else None
    review_payload = {
        "id": review_id,
        "order_id": payload.order_id,
        "listing_id": payload.listing_id,
        "reviewer_user_id": user["entity_id"],
        "seller_user_id": seller_user_id,
        "rating": payload.rating,
        "content": payload.content,
        "is_anonymous": payload.anonymity_enabled,
        "status": "published",
        "created_at": now,
        "updated_at": now,
    }
    store.upsert_record("review", review_id, review_payload)
    for index, asset_id in enumerate(payload.media_asset_ids):
        store.upsert_record(
            "review_media",
            f"review_media_{review_id}_{index + 1}",
            {
                "id": f"review_media_{review_id}_{index + 1}",
                "review_id": review_id,
                "asset": {
                    "id": asset_id,
                    "kind": "image",
                    "url": f"/storage/uploads/{asset_id}",
                    "thumbnail_url": None,
                    "width": None,
                    "height": None,
                    "mime_type": None,
                    "sort_order": index,
                },
                "sort_order": index,
            },
            parent_id=review_id,
        )
    for index, tag_name in enumerate(payload.tags):
        tag_record = store.find_first("review_tag", predicate=lambda item, name=tag_name: item["payload"].get("tag_key") == name or item["payload"].get("display_name") == name)
        if tag_record is None:
            tag_record = {
                "entity_id": f"review_tag_custom_{index + 1}",
                "payload": {
                    "id": f"review_tag_custom_{index + 1}",
                    "tag_key": tag_name,
                    "display_name": tag_name,
                    "tag_group": "custom",
                    "active": True,
                },
            }
            store.upsert_record("review_tag", tag_record["entity_id"], tag_record["payload"])
        store.upsert_record(
            "review_tag_link",
            f"review_tag_link_{review_id}_{index + 1}",
            {"review_id": review_id, "tag_id": tag_record["entity_id"]},
            parent_id=review_id,
        )
    return ok(request, _review_summary(store, store.get_record("review", review_id) or {"entity_id": review_id, "payload": review_payload}))


@router.get("/reviews/{review_id}")
def review_detail(request: Request, review_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    review = store.get_record("review", review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在。")
    return ok(request, _review_summary(store, review))


@router.post("/reviews/drafts")
def create_review_draft(request: Request, payload: ReviewCreateRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    draft_id = _new_id("review_draft")
    now = _now()
    draft_payload = {
        "id": draft_id,
        "user_id": user["entity_id"],
        "order_id": payload.order_id,
        "listing_id": payload.listing_id,
        "rating": payload.rating,
        "tags": list(payload.tags),
        "content": payload.content,
        "media_asset_ids": list(payload.media_asset_ids),
        "anonymity_enabled": payload.anonymity_enabled,
        "created_at": now,
        "updated_at": now,
    }
    store.upsert_record("review_draft", draft_id, draft_payload, parent_id=user["entity_id"])
    return ok(request, draft_payload)


@router.get("/reviews/drafts/{draft_id}")
def review_draft_detail(request: Request, draft_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    draft = store.get_record("review_draft", draft_id)
    if draft is None or (draft["payload"].get("user_id") or draft["parent_id"]) != user["entity_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论草稿不存在。")
    return ok(request, draft["payload"])


@router.patch("/reviews/drafts/{draft_id}")
def review_draft_update(request: Request, draft_id: str, payload: ReviewDraftUpdateRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user = _require_current_user(store, request)
    draft = store.get_record("review_draft", draft_id)
    if draft is None or (draft["payload"].get("user_id") or draft["parent_id"]) != user["entity_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论草稿不存在。")
    updated = dict(draft["payload"])
    updated.update(payload.model_dump(exclude_none=True))
    updated["updated_at"] = _now()
    store.upsert_record("review_draft", draft_id, updated, parent_id=user["entity_id"])
    return ok(request, updated)


@router.get("/wallet")
def wallet(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    account = store.find_first("wallet_account", predicate=lambda item: item["payload"].get("user_id") == user_id)
    transactions = []
    if account is not None:
        transactions = [
            {
                "id": item["entity_id"],
                "wallet_account_id": item["payload"].get("wallet_account_id"),
                "transaction_type": item["payload"].get("transaction_type") or "unknown",
                "amount": _money(item["payload"].get("amount_minor"), item["payload"].get("currency")),
                "reference_type": item["payload"].get("reference_type"),
                "reference_id": item["payload"].get("reference_id"),
                "status": item["payload"].get("status") or "posted",
                "created_at": item["payload"].get("created_at"),
            }
            for item in store.list_records("wallet_transaction", parent_id=account["entity_id"])
        ]
    return ok(request, {"account": _wallet_summary(account) if account else None, "transactions": transactions})


@router.get("/wallet/transactions")
def wallet_transactions(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    account = store.find_first("wallet_account", predicate=lambda item: item["payload"].get("user_id") == user_id)
    if account is None:
        return ok(request, [])
    transactions = [
        {
            "id": item["entity_id"],
            "wallet_account_id": item["payload"].get("wallet_account_id"),
            "transaction_type": item["payload"].get("transaction_type") or "unknown",
            "amount": _money(item["payload"].get("amount_minor"), item["payload"].get("currency")),
            "reference_type": item["payload"].get("reference_type"),
            "reference_id": item["payload"].get("reference_id"),
            "status": item["payload"].get("status") or "posted",
            "created_at": item["payload"].get("created_at"),
        }
        for item in store.list_records("wallet_transaction", parent_id=account["entity_id"])
    ]
    return ok(request, transactions)


@router.get("/membership/plans")
def membership_plans(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    plans = []
    for item in store.list_records("membership_plan"):
        payload = item["payload"]
        plans.append(
            {
                "id": item["entity_id"],
                "plan_key": payload.get("plan_key") or "",
                "title": payload.get("title") or "",
                "price": _money(payload.get("price_minor"), payload.get("currency")),
                "benefits_json": list(payload.get("benefits_json") or []),
                "active": bool(payload.get("active", True)),
            }
        )
    return ok(request, plans)


@router.get("/membership/subscription")
def membership_subscription(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    subscription = store.find_first("membership_subscription", predicate=lambda item: item["payload"].get("user_id") == user_id)
    if subscription is None:
        return ok(request, None)
    plan = store.get_record("membership_plan", subscription["payload"].get("plan_id") or "")
    plan_payload = plan["payload"] if plan else {}
    return ok(request, {
        "id": subscription["entity_id"],
        "user_id": subscription["payload"].get("user_id"),
        "plan": {
            "id": plan["entity_id"] if plan else None,
            "plan_key": plan_payload.get("plan_key"),
            "title": plan_payload.get("title"),
            "price": _money(plan_payload.get("price_minor"), plan_payload.get("currency")),
            "benefits_json": list(plan_payload.get("benefits_json") or []),
            "active": bool(plan_payload.get("active", True)),
        },
        "status": subscription["payload"].get("status") or "active",
        "started_at": subscription["payload"].get("started_at"),
        "expires_at": subscription["payload"].get("expires_at"),
    })


@router.post("/membership/upgrade")
def membership_upgrade(request: Request, payload: MembershipUpgradeRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    plan = store.find_first("membership_plan", predicate=lambda item: item["payload"].get("plan_key") == payload.plan_key)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会员方案不存在。")
    user_id = _require_current_user_id(store, request)
    subscription_id = f"subscription_{user_id}"
    now = _now()
    subscription_payload = {
        "id": subscription_id,
        "user_id": user_id,
        "plan_id": plan["entity_id"],
        "status": "active",
        "started_at": now,
        "expires_at": None,
        "created_at": now,
        "updated_at": now,
    }
    store.upsert_record("membership_subscription", subscription_id, subscription_payload, parent_id=user_id)
    return ok(request, {
        "id": subscription_id,
        "user_id": user_id,
        "plan": {
            "id": plan["entity_id"],
            "plan_key": plan["payload"].get("plan_key"),
            "title": plan["payload"].get("title"),
            "price": _money(plan["payload"].get("price_minor"), plan["payload"].get("currency")),
            "benefits_json": list(plan["payload"].get("benefits_json") or []),
            "active": bool(plan["payload"].get("active", True)),
        },
        "status": "active",
        "started_at": now,
        "expires_at": None,
    })


@router.get("/notifications")
def notifications(
    request: Request,
    store: MarketplaceStore = Depends(get_store),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    items = [_notification_summary(item) for item in store.list_records("notification") if item["payload"].get("user_id") == user_id]
    page_items, page_meta = store.paginate(items, page=page, page_size=page_size)
    return ok(request, page_items, page=page_meta)


@router.get("/badges/summary")
def badge_summary(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    return ok(request, store.badge_summary_payload(user_id))


@router.get("/notifications/badge")
def notification_badge(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    return badge_summary(request, store)


@router.post("/notifications/read")
def read_notifications(request: Request, payload: NotificationReadRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    read_at = payload.read_at or _now()
    updated_count = 0
    for item in store.list_records("notification"):
        if item["payload"].get("user_id") != user_id or item["payload"].get("read_at") is not None:
            continue
        payload_dict = dict(item["payload"])
        payload_dict["read_at"] = read_at
        store.upsert_record("notification", item["entity_id"], payload_dict)
        updated_count += 1
    return ok(request, {"read_count": updated_count, "read_at": read_at})


@router.patch("/notifications/{notification_id}/read")
def read_notification(request: Request, notification_id: str, payload: NotificationReadRequest, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    user_id = _require_current_user_id(store, request)
    notification = store.get_record("notification", notification_id)
    if notification is None or notification["payload"].get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在。")
    updated = dict(notification["payload"])
    updated["read_at"] = payload.read_at or _now()
    store.upsert_record("notification", notification_id, updated)
    return ok(request, updated)


@router.get("/pages/orders")
def page_orders(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    _require_current_user_id(store, request)
    return ok(request, _page("orders", title="订单中心", subtitle="查看买卖双方的订单状态与物流进度。", resources={"orders": orders(request, store, page=1, page_size=DEFAULT_PAGE_SIZE)["data"]}))


@router.get("/pages/orders/{order_id}")
def page_order_detail(request: Request, order_id: str, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    order = order_detail(request, order_id, store)["data"]
    return ok(request, _page("order_detail", title="订单详情", subtitle="查看支付、物流与收货进度。", resources=order))


@router.get("/pages/wallet")
def page_wallet(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    _require_current_user_id(store, request)
    return ok(request, _page("wallet", title="钱包", subtitle="查看余额、冻结金额和资金流水。", resources=wallet(request, store)["data"]))


@router.get("/pages/membership")
def page_membership(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    _require_current_user_id(store, request)
    return ok(request, _page("membership", title="会员中心", subtitle="升级会员以获得推荐、展示和客服权益。", resources={"plans": membership_plans(request, store)["data"], "subscription": membership_subscription(request, store)["data"]}))


@router.get("/pages/messages")
def page_messages(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    _require_current_user_id(store, request)
    return ok(request, _page("messages", title="消息", subtitle="和买家卖家保持沟通。", resources={"conversations": conversations(request, store, page=1, page_size=DEFAULT_PAGE_SIZE)["data"]}))


@router.get("/pages/notifications")
def page_notifications(request: Request, store: MarketplaceStore = Depends(get_store)) -> dict[str, Any]:
    _require_current_user_id(store, request)
    return ok(request, _page("notifications", title="通知", subtitle="查看订单、消息和系统通知。", resources={"notifications": notifications(request, store, page=1, page_size=DEFAULT_PAGE_SIZE)["data"], "badge": badge_summary(request, store)["data"]}))

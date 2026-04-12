from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from shared.config import BUSINESS_DB_PATH, TRAINER_SERVICE_BASE_URL, TRAINER_SERVICE_PUBLIC_BASE_URL

RECORD_TYPES = {
    "user",
    "user_profile",
    "user_consent",
    "login_attempt",
    "auth_session",
    "category",
    "listing",
    "listing_media",
    "listing_spec",
    "listing_draft",
    "listing_favorite",
    "conversation",
    "conversation_member",
    "message",
    "order",
    "order_item",
    "order_event",
    "shipment",
    "shipment_event",
    "review",
    "review_media",
    "review_tag",
    "review_tag_link",
    "wallet_account",
    "wallet_transaction",
    "membership_plan",
    "membership_subscription",
    "notification",
    "banner",
    "home_section",
    "service_card",
    "feature_flag",
    "app_config",
    "user_follow",
    "user_address",
    "user_stat",
    "search_suggestion",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _json_loads(payload: str | None, default: Any = None) -> Any:
    if payload is None or payload == "":
        return default
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return default


def _hash_password(password: str) -> str:
    iterations = 200_000
    salt = os.urandom(16)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived_key.hex()}"


def _legacy_hash_password(password: str) -> str:
    digest = hashlib.sha256()
    digest.update(password.encode("utf-8"))
    return digest.hexdigest()


def _verify_password_hash(password: str, encoded_hash: str | None) -> bool:
    if not encoded_hash:
        return False

    if encoded_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations_raw, salt_hex, expected_hex = encoded_hash.split("$", 3)
            iterations = int(iterations_raw)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(expected_hex)
        except (ValueError, TypeError):
            return False
        derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived_key, expected)

    return hmac.compare_digest(_legacy_hash_password(password), encoded_hash)


def _generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class MarketplaceStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or BUSINESS_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._configure_connection()
        self._ensure_schema()
        self._seed_if_needed()

    def _configure_connection(self) -> None:
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = NORMAL")
        self.connection.execute("PRAGMA busy_timeout = 3000")

    def _ensure_schema(self) -> None:
        existing_columns = self.connection.execute("PRAGMA table_info(records)").fetchall()
        if existing_columns:
            pk_columns = [row["name"] for row in sorted(existing_columns, key=lambda item: item["pk"]) if row["pk"]]
            if pk_columns != ["entity_type", "entity_id"]:
                self.connection.execute("DROP TABLE IF EXISTS records")
                self.connection.commit()
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS records (
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                parent_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (entity_type, entity_id)
            );

            CREATE INDEX IF NOT EXISTS idx_records_type_parent_created
                ON records(entity_type, parent_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_records_type_created
                ON records(entity_type, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_records_parent
                ON records(parent_id);
            """
        )
        self.connection.commit()

    def _seed_if_needed(self) -> None:
        if self.count_records("user") > 0:
            return
        self.seed_demo_data()

    def close(self) -> None:
        try:
            self.connection.close()
        except sqlite3.Error:
            pass

    def count_records(self, entity_type: str | None = None) -> int:
        if entity_type is None:
            row = self.connection.execute("SELECT COUNT(*) AS count FROM records").fetchone()
        else:
            row = self.connection.execute(
                "SELECT COUNT(*) AS count FROM records WHERE entity_type = ?",
                (entity_type,),
            ).fetchone()
        return int(row["count"] if row else 0)

    def list_records(self, entity_type: str, parent_id: str | None = None) -> list[dict[str, Any]]:
        if parent_id is None:
            rows = self.connection.execute(
                "SELECT * FROM records WHERE entity_type = ? ORDER BY created_at DESC",
                (entity_type,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM records WHERE entity_type = ? AND parent_id = ? ORDER BY created_at DESC",
                (entity_type, parent_id),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_record(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM records WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def find_first(self, entity_type: str, *, predicate: Any | None = None) -> dict[str, Any] | None:
        for record in self.list_records(entity_type):
            if predicate is None or predicate(record):
                return record
        return None

    def upsert_record(
        self,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        *,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        payload_json = _json_dumps(payload)
        self.connection.execute(
            """
            INSERT INTO records (entity_type, entity_id, parent_id, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                entity_type = excluded.entity_type,
                parent_id = excluded.parent_id,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (entity_type, entity_id, parent_id, payload_json, now, now),
        )
        self.connection.commit()
        record = self.get_record(entity_type, entity_id)
        if record is None:
            raise RuntimeError(f"Failed to persist record {entity_type}:{entity_id}")
        return record

    def delete_record(self, entity_type: str, entity_id: str) -> None:
        self.connection.execute(
            "DELETE FROM records WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        )
        self.connection.commit()

    def _row_to_record(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "parent_id": row["parent_id"],
            "payload": _json_loads(row["payload_json"], default={}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _seed(self, entity_type: str, entity_id: str, payload: dict[str, Any], parent_id: str | None = None) -> None:
        self.upsert_record(entity_type, entity_id, payload, parent_id=parent_id)

    def seed_demo_data(self) -> None:
        now = _utc_now()
        demo_buyer_id = "user_demo_buyer"
        demo_seller_id = "user_demo_seller"
        demo_support_id = "user_demo_support"

        users = [
            {
                "entity_id": demo_buyer_id,
                "identifier": "demo-buyer",
                "password_hash": _hash_password("demo12345"),
                "display_name": "Demo Buyer",
                "avatar_url": "/storage/seed/avatars/buyer.png",
                "bio": "热爱淘货的买家示例",
                "location": "Beijing",
                "sesame_credit_score": 712,
                "vip_level": "gold",
                "profile_visibility": "public",
                "birth_date": "1996-08-12",
                "status": "active",
                "registered_at": now,
                "last_login_at": now,
                "password_updated_at": now,
                "account_locked_until": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "entity_id": demo_seller_id,
                "identifier": "demo-seller",
                "password_hash": _hash_password("demo12345"),
                "display_name": "Demo Seller",
                "avatar_url": "/storage/seed/avatars/seller.png",
                "bio": "从事二手数码与家居发布",
                "location": "Shanghai",
                "sesame_credit_score": 756,
                "vip_level": "silver",
                "profile_visibility": "public",
                "birth_date": "1992-03-04",
                "status": "active",
                "registered_at": now,
                "last_login_at": now,
                "password_updated_at": now,
                "account_locked_until": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "entity_id": demo_support_id,
                "identifier": "support@example.com",
                "password_hash": _hash_password("support12345"),
                "display_name": "Support Bot",
                "avatar_url": "/storage/seed/avatars/support.png",
                "bio": "客服与系统通知示例账号",
                "location": "Remote",
                "sesame_credit_score": 900,
                "vip_level": "none",
                "profile_visibility": "private",
                "birth_date": None,
                "status": "active",
                "registered_at": now,
                "last_login_at": now,
                "password_updated_at": now,
                "account_locked_until": None,
                "created_at": now,
                "updated_at": now,
            },
        ]
        for user in users:
            self._seed("user", user["entity_id"], user)
            profile = {
                "id": user["entity_id"],
                "display_name": user["display_name"],
                "avatar_url": user["avatar_url"],
                "birth_date": user["birth_date"],
                "age_years": self._calculate_age(user["birth_date"]),
                "bio": user["bio"],
                "location": user["location"],
                "sesame_credit_score": user["sesame_credit_score"],
                "vip_level": user["vip_level"],
                "profile_visibility": user["profile_visibility"],
                "updated_at": now,
            }
            self._seed("user_profile", user["entity_id"], profile)
            self._seed(
                "user_consent",
                f"consent_{user['entity_id']}",
                {
                    "id": f"consent_{user['entity_id']}",
                    "user_id": user["entity_id"],
                    "consent_type": "terms_and_privacy",
                    "consent_version": "v1",
                    "accepted_at": now,
                    "metadata_json": {"source": "seed"},
                },
                parent_id=user["entity_id"],
            )

        categories = [
            ("cat_tech", "electronics", "数码电子", "electronics", "device", 1),
            ("cat_home", "home", "居家生活", "home", "home", 2),
            ("cat_fashion", "fashion", "时尚配饰", "fashion", "shirt", 3),
            ("cat_book", "books", "图书文具", "books", "book", 4),
            ("cat_sport", "sport", "运动户外", "sport", "sport", 5),
            ("cat_other", "other", "其他闲置", "other", "more", 6),
        ]
        for entity_id, slug, name, icon, sort_order, active in categories:
            self._seed(
                "category",
                entity_id,
                {
                    "id": entity_id,
                    "parent_id": None,
                    "name": name,
                    "slug": slug,
                    "icon_key": icon,
                    "sort_order": sort_order,
                    "active": True,
                    "listing_count": 0,
                },
            )

        listings = [
            {
                "id": "listing_camera_1",
                "seller_id": demo_seller_id,
                "category_id": "cat_tech",
                "title": "Sony Alpha 7C 二手微单",
                "subtitle": "成色良好，适合视频创作",
                "description": "二手微单相机，适合记录商品视频和日常拍摄。",
                "price_minor": 529900,
                "original_price_minor": 699900,
                "currency": "CNY",
                "status": "live",
                "condition_level": "excellent",
                "location_city": "Shanghai",
                "cover_media_json": {
                    "id": "media_listing_camera_1_cover",
                    "kind": "image",
                    "url": "/storage/seed/listings/camera_cover.jpg",
                    "thumbnail_url": "/storage/seed/listings/camera_cover_thumb.jpg",
                    "width": 1200,
                    "height": 900,
                    "mime_type": "image/jpeg",
                    "sort_order": 0,
                },
                "badges_json": ["verified", "nearby"],
                "model_url": None,
                "model_ply_url": None,
                "model_sog_url": None,
                "model_format": None,
                "viewer_url": None,
                "log_url": None,
                "remote_task_id": None,
                "object_masking": False,
                "quality_profile": None,
                "published_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "listing_chair_1",
                "seller_id": demo_seller_id,
                "category_id": "cat_home",
                "title": "北欧风人体工学椅",
                "subtitle": "办公室和游戏都适合",
                "description": "高度可调，头枕完整，适合长时间坐姿。",
                "price_minor": 139900,
                "original_price_minor": 299900,
                "currency": "CNY",
                "status": "live",
                "condition_level": "good",
                "location_city": "Shanghai",
                "cover_media_json": {
                    "id": "media_listing_chair_1_cover",
                    "kind": "image",
                    "url": "/storage/seed/listings/chair_cover.jpg",
                    "thumbnail_url": "/storage/seed/listings/chair_cover_thumb.jpg",
                    "width": 1200,
                    "height": 900,
                    "mime_type": "image/jpeg",
                    "sort_order": 0,
                },
                "badges_json": ["popular"],
                "model_url": None,
                "model_ply_url": None,
                "model_sog_url": None,
                "model_format": None,
                "viewer_url": None,
                "log_url": None,
                "remote_task_id": None,
                "object_masking": False,
                "quality_profile": None,
                "published_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "listing_bag_1",
                "seller_id": demo_seller_id,
                "category_id": "cat_fashion",
                "title": "通勤单肩包",
                "subtitle": "轻便百搭",
                "description": "适合通勤和短途出行，内袋完整。",
                "price_minor": 89900,
                "original_price_minor": 159900,
                "currency": "CNY",
                "status": "reserved",
                "condition_level": "good",
                "location_city": "Beijing",
                "cover_media_json": {
                    "id": "media_listing_bag_1_cover",
                    "kind": "image",
                    "url": "/storage/seed/listings/bag_cover.jpg",
                    "thumbnail_url": "/storage/seed/listings/bag_cover_thumb.jpg",
                    "width": 1200,
                    "height": 900,
                    "mime_type": "image/jpeg",
                    "sort_order": 0,
                },
                "badges_json": ["hot"],
                "model_url": None,
                "model_ply_url": None,
                "model_sog_url": None,
                "model_format": None,
                "viewer_url": None,
                "log_url": None,
                "remote_task_id": None,
                "object_masking": False,
                "quality_profile": None,
                "published_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "listing_3dgs_demo",
                "seller_id": demo_seller_id,
                "category_id": "cat_home",
                "title": "3D 展示演示商品",
                "subtitle": "用于联动远程 3DGS 训练服务",
                "description": "该商品记录保留 3D 模型相关字段，用于后续接入远程 3DGS 训练服务。",
                "price_minor": 29900,
                "original_price_minor": 49900,
                "currency": "CNY",
                "status": "draft",
                "condition_level": "new",
                "location_city": "Remote",
                "cover_media_json": {
                    "id": "media_listing_3dgs_demo_cover",
                    "kind": "image",
                    "url": "/storage/seed/listings/3dgs_cover.jpg",
                    "thumbnail_url": "/storage/seed/listings/3dgs_cover_thumb.jpg",
                    "width": 1200,
                    "height": 900,
                    "mime_type": "image/jpeg",
                    "sort_order": 0,
                },
                "badges_json": ["3d-ready"],
                "model_url": None,
                "model_ply_url": None,
                "model_sog_url": None,
                "model_format": None,
                "viewer_url": None,
                "log_url": None,
                "remote_task_id": None,
                "object_masking": True,
                "quality_profile": "balanced",
                "published_at": None,
                "created_at": now,
                "updated_at": now,
            },
        ]
        for listing in listings:
            self._seed("listing", listing["id"], listing)

        listing_media = [
            ("media_camera_1_1", "listing_camera_1", "image", "/storage/seed/listings/camera_1.jpg", 1),
            ("media_camera_1_2", "listing_camera_1", "image", "/storage/seed/listings/camera_2.jpg", 2),
            ("media_chair_1_1", "listing_chair_1", "image", "/storage/seed/listings/chair_1.jpg", 1),
            ("media_bag_1_1", "listing_bag_1", "image", "/storage/seed/listings/bag_1.jpg", 1),
            ("media_3dgs_demo_1", "listing_3dgs_demo", "video", "/storage/seed/listings/3dgs_demo.mp4", 1),
        ]
        for media_id, listing_id, kind, url, sort_order in listing_media:
            self._seed(
                "listing_media",
                media_id,
                {
                    "id": media_id,
                    "listing_id": listing_id,
                    "kind": kind,
                    "url": url,
                    "thumbnail_url": url,
                    "width": 1200,
                    "height": 900,
                    "mime_type": "image/jpeg" if kind == "image" else "video/mp4",
                    "sort_order": sort_order,
                    "is_cover": sort_order == 1,
                    "created_at": now,
                    "updated_at": now,
                },
                parent_id=listing_id,
            )

        listing_specs = [
            ("spec_camera_brand", "listing_camera_1", "品牌", "Sony", 1),
            ("spec_camera_body", "listing_camera_1", "机身", "全画幅", 2),
            ("spec_chair_material", "listing_chair_1", "材质", "网布+金属", 1),
            ("spec_bag_style", "listing_bag_1", "风格", "通勤", 1),
            ("spec_3dgs_model", "listing_3dgs_demo", "模型状态", "待训练", 1),
        ]
        for spec_id, listing_id, key, value, sort_order in listing_specs:
            self._seed(
                "listing_spec",
                spec_id,
                {
                    "spec_key": key,
                    "spec_value": value,
                    "sort_order": sort_order,
                },
                parent_id=listing_id,
            )

        draft_payload = {
            "title": "待发布 3D 商品",
            "subtitle": "示例草稿",
            "description": "用于卖家发布流测试。",
            "price_minor": 19900,
            "original_price_minor": 29900,
            "currency": "CNY",
            "condition_level": "good",
            "location_city": "Hangzhou",
            "category_id": "cat_home",
            "remote_task_id": None,
            "model_url": None,
            "viewer_url": None,
        }
        self._seed(
            "listing_draft",
            "draft_demo_1",
            {
                "id": "draft_demo_1",
                "seller_id": demo_seller_id,
                "category_id": "cat_home",
                "title": draft_payload["title"],
                "subtitle": draft_payload["subtitle"],
                "description": draft_payload["description"],
                "price_minor": draft_payload["price_minor"],
                "original_price_minor": draft_payload["original_price_minor"],
                "currency": draft_payload["currency"],
                "status": "draft",
                "condition_level": draft_payload["condition_level"],
                "location_city": draft_payload["location_city"],
                "draft_payload_json": draft_payload,
                "created_at": now,
                "updated_at": now,
            },
        )

        favorites = [
            (demo_buyer_id, "listing_camera_1"),
            (demo_buyer_id, "listing_chair_1"),
        ]
        for user_id, listing_id in favorites:
            self._seed(
                "listing_favorite",
                f"favorite_{user_id}_{listing_id}",
                {"user_id": user_id, "listing_id": listing_id, "created_at": now},
                parent_id=listing_id,
            )

        conversation_id = "conversation_demo_1"
        self._seed(
            "conversation",
            conversation_id,
            {
                "id": conversation_id,
                "listing_id": "listing_camera_1",
                "buyer_id": demo_buyer_id,
                "seller_id": demo_seller_id,
                "status": "active",
                "last_message_preview": "这台相机还可以再优惠一点吗？",
                "unread_count": 1,
                "updated_at": now,
                "last_message_at": now,
            },
        )
        self._seed(
            "conversation_member",
            f"member_{conversation_id}_{demo_buyer_id}",
            {
                "conversation_id": conversation_id,
                "user_id": demo_buyer_id,
                "role": "buyer",
                "last_read_message_id": None,
                "unread_count": 0,
            },
            parent_id=conversation_id,
        )
        self._seed(
            "conversation_member",
            f"member_{conversation_id}_{demo_seller_id}",
            {
                "conversation_id": conversation_id,
                "user_id": demo_seller_id,
                "role": "seller",
                "last_read_message_id": None,
                "unread_count": 1,
            },
            parent_id=conversation_id,
        )
        messages = [
            (
                "message_1",
                conversation_id,
                demo_buyer_id,
                {
                    "id": "message_1",
                    "conversation_id": conversation_id,
                    "sender_id": demo_buyer_id,
                    "message_type": "text",
                    "content_text": "这台相机还可以再优惠一点吗？",
                    "asset": None,
                    "created_at": now,
                    "read_at": None,
                },
            ),
            (
                "message_2",
                conversation_id,
                demo_seller_id,
                {
                    "id": "message_2",
                    "conversation_id": conversation_id,
                    "sender_id": demo_seller_id,
                    "message_type": "text",
                    "content_text": "可以，成交我再送一块原装电池。",
                    "asset": None,
                    "created_at": now,
                    "read_at": None,
                },
            ),
        ]
        for message_id, parent_id, sender_id, payload in messages:
            self._seed("message", message_id, payload, parent_id=parent_id)

        order_id = "order_demo_1"
        order_snapshot = {
            "listing_id": "listing_camera_1",
            "title": "Sony Alpha 7C 二手微单",
            "price_minor": 529900,
            "currency": "CNY",
            "cover_asset_id": "media_camera_1_1",
            "seller_display_name": "Demo Seller",
        }
        logistics_snapshot = {
            "carrier_name": "顺丰速运",
            "tracking_no": "SF123456789CN",
            "status": "shipped",
            "shipped_at": now,
            "estimated_delivery_at": now,
            "address": {
                "receiver_name": "Demo Buyer",
                "phone": "13800000000",
                "region": "Beijing / Beijing / Haidian",
                "detail": "Demo Road 1",
            },
        }
        self._seed(
            "order",
            order_id,
            {
                "id": order_id,
                "order_no": "ORD-20260411-0001",
                "buyer_id": demo_buyer_id,
                "seller_id": demo_seller_id,
                "listing_id": "listing_camera_1",
                "status": "shipped",
                "payment_status": "paid",
                "shipping_status": "shipped",
                "currency": "CNY",
                "subtotal_minor": 529900,
                "shipping_minor": 0,
                "discount_minor": 10000,
                "total_minor": 519900,
                "can_confirm_receipt": True,
                "item_snapshot_json": order_snapshot,
                "logistics_json": logistics_snapshot,
                "created_at": now,
                "updated_at": now,
            },
        )
        self._seed(
            "order_item",
            f"order_item_{order_id}_1",
            {
                "id": f"order_item_{order_id}_1",
                "order_id": order_id,
                "listing_id": "listing_camera_1",
                "snapshot_title": order_snapshot["title"],
                "snapshot_price_minor": order_snapshot["price_minor"],
                "snapshot_currency": order_snapshot["currency"],
                "snapshot_cover_asset_id": order_snapshot["cover_asset_id"],
                "quantity": 1,
                "created_at": now,
                "updated_at": now,
            },
            parent_id=order_id,
        )
        self._seed(
            "order_event",
            f"order_event_{order_id}_1",
            {
                "id": f"order_event_{order_id}_1",
                "order_id": order_id,
                "status": "paid",
                "event_note": "订单已支付",
                "actor_user_id": demo_buyer_id,
                "occurred_at": now,
            },
            parent_id=order_id,
        )
        self._seed(
            "order_event",
            f"order_event_{order_id}_2",
            {
                "id": f"order_event_{order_id}_2",
                "order_id": order_id,
                "status": "shipped",
                "event_note": "卖家已发货",
                "actor_user_id": demo_seller_id,
                "occurred_at": now,
            },
            parent_id=order_id,
        )
        shipment_id = "shipment_demo_1"
        self._seed(
            "shipment",
            shipment_id,
            {
                "id": shipment_id,
                "order_id": order_id,
                "carrier_name": "顺丰速运",
                "tracking_no": "SF123456789CN",
                "status": "in_transit",
                "shipped_at": now,
                "estimated_delivery_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )
        self._seed(
            "shipment_event",
            f"shipment_event_{shipment_id}_1",
            {
                "id": f"shipment_event_{shipment_id}_1",
                "shipment_id": shipment_id,
                "event_code": "picked_up",
                "event_text": "快递员已揽收",
                "event_city": "Shanghai",
                "occurred_at": now,
            },
            parent_id=shipment_id,
        )
        self._seed(
            "shipment_event",
            f"shipment_event_{shipment_id}_2",
            {
                "id": f"shipment_event_{shipment_id}_2",
                "shipment_id": shipment_id,
                "event_code": "in_transit",
                "event_text": "包裹运输中",
                "event_city": "Nanjing",
                "occurred_at": now,
            },
            parent_id=shipment_id,
        )

        self._seed(
            "review",
            "review_demo_1",
            {
                "id": "review_demo_1",
                "order_id": order_id,
                "listing_id": "listing_camera_1",
                "reviewer_user_id": demo_buyer_id,
                "seller_user_id": demo_seller_id,
                "rating": 5,
                "content": "商品描述准确，包装完整，交易很顺利。",
                "is_anonymous": False,
                "status": "published",
                "created_at": now,
                "updated_at": now,
            },
        )
        self._seed(
            "review_media",
            "review_media_demo_1",
            {
                "id": "review_media_demo_1",
                "review_id": "review_demo_1",
                "asset": {
                    "id": "review_media_asset_demo_1",
                    "kind": "image",
                    "url": "/storage/seed/reviews/review_1.jpg",
                    "thumbnail_url": "/storage/seed/reviews/review_1_thumb.jpg",
                    "width": 1200,
                    "height": 900,
                    "mime_type": "image/jpeg",
                    "sort_order": 0,
                },
                "sort_order": 0,
            },
            parent_id="review_demo_1",
        )

        tags = [
            ("review_tag_fast_ship", "发货快", "shipping"),
            ("review_tag_match", "与描述一致", "quality"),
            ("review_tag_polite", "沟通顺畅", "service"),
            ("review_tag_good_pack", "包装完整", "shipping"),
        ]
        for tag_id, tag_key, display_name in tags:
            self._seed(
                "review_tag",
                tag_id,
                {
                    "id": tag_id,
                    "tag_key": tag_key,
                    "display_name": display_name,
                    "tag_group": "general",
                    "active": True,
                },
            )
        self._seed(
            "review_tag_link",
            "review_tag_link_1",
            {"review_id": "review_demo_1", "tag_id": "review_tag_match"},
            parent_id="review_demo_1",
        )
        self._seed(
            "review_tag_link",
            "review_tag_link_2",
            {"review_id": "review_demo_1", "tag_id": "review_tag_good_pack"},
            parent_id="review_demo_1",
        )

        self._seed(
            "wallet_account",
            f"wallet_{demo_buyer_id}",
            {
                "id": f"wallet_{demo_buyer_id}",
                "user_id": demo_buyer_id,
                "available_minor": 120000,
                "held_minor": 0,
                "currency": "CNY",
                "status": "active",
            },
        )
        self._seed(
            "wallet_account",
            f"wallet_{demo_seller_id}",
            {
                "id": f"wallet_{demo_seller_id}",
                "user_id": demo_seller_id,
                "available_minor": 550000,
                "held_minor": 0,
                "currency": "CNY",
                "status": "active",
            },
        )
        self._seed(
            "wallet_transaction",
            "wallet_tx_1",
            {
                "id": "wallet_tx_1",
                "wallet_account_id": f"wallet_{demo_buyer_id}",
                "transaction_type": "payment",
                "amount_minor": 519900,
                "currency": "CNY",
                "reference_type": "order",
                "reference_id": order_id,
                "status": "posted",
                "created_at": now,
            },
        )

        plan = {
            "id": "plan_gold_1",
            "plan_key": "gold",
            "title": "Gold 会员",
            "price_minor": 9900,
            "currency": "CNY",
            "benefits_json": ["优先推荐", "高亮展示", "专属客服"],
            "active": True,
        }
        self._seed("membership_plan", plan["id"], plan)
        self._seed(
            "membership_subscription",
            "subscription_demo_buyer",
            {
                "id": "subscription_demo_buyer",
                "user_id": demo_buyer_id,
                "plan_id": plan["id"],
                "status": "active",
                "started_at": now,
                "expires_at": None,
                "created_at": now,
                "updated_at": now,
            },
        )

        banners = [
            ("banner_1", "3D 展示上新", "让闲置商品更有表现力", 1),
            ("banner_2", "精选好物", "今日推荐二手数码与家居", 2),
        ]
        for banner_id, title, subtitle, sort_order in banners:
            self._seed(
                "banner",
                banner_id,
                {
                    "id": banner_id,
                    "title": title,
                    "subtitle": subtitle,
                    "media": {
                        "id": f"media_{banner_id}",
                        "kind": "image",
                        "url": "/storage/seed/banners/banner.jpg",
                        "thumbnail_url": "/storage/seed/banners/banner_thumb.jpg",
                        "width": 1920,
                        "height": 1080,
                        "mime_type": "image/jpeg",
                        "sort_order": 0,
                    },
                    "action_type": "route",
                    "action_ref": "/pages/home",
                    "sort_order": sort_order,
                    "active": True,
                },
            )

        home_sections = [
            {
                "id": "home_featured",
                "section_key": "featured",
                "section_type": "hero",
                "title": "精选推荐",
                "subtitle": "每天都有新鲜闲置",
                "priority": 1,
                "payload_json": {"items": ["listing_camera_1", "listing_chair_1"]},
                "active": True,
            },
            {
                "id": "home_categories",
                "section_key": "categories",
                "section_type": "grid",
                "title": "分类浏览",
                "subtitle": "快速找到想要的品类",
                "priority": 2,
                "payload_json": {"items": ["cat_tech", "cat_home", "cat_fashion", "cat_book"]},
                "active": True,
            },
        ]
        for section in home_sections:
            self._seed("home_section", section["id"], section)

        services = [
            ("service_sell", "我要卖", "sell", "route", "/pages/sell", 1),
            ("service_orders", "订单", "receipt", "route", "/pages/orders", 2),
            ("service_wallet", "钱包", "wallet", "route", "/pages/wallet", 3),
            ("service_membership", "会员", "vip", "route", "/pages/membership", 4),
        ]
        for service_id, title, icon, destination_type, destination_ref, sort_order in services:
            self._seed(
                "service_card",
                service_id,
                {
                    "id": service_id,
                    "service_key": service_id,
                    "title": title,
                    "icon": icon,
                    "badge": None,
                    "description": None,
                    "destination_type": destination_type,
                    "destination_ref": destination_ref,
                    "sort_order": sort_order,
                    "active": True,
                },
            )

        self._seed(
            "feature_flag",
            "flag_guest_entry",
            {
                "flag_key": "guest_entry_enabled",
                "enabled": True,
                "target_scope": "public",
                "payload_json": {},
            },
        )
        self._seed(
            "app_config",
            "public_config",
            {
                "config_key": "public_config",
                "config_value_json": {
                    "api_version": "v1",
                    "base_currency": "CNY",
                    "guest_entry_enabled": True,
                    "supported_locales": ["zh-CN", "en-US"],
                },
                "active": True,
            },
        )

        self._seed(
            "auth_session",
            "session_demo_buyer",
            {
                "id": "session_demo_buyer",
                "user_id": demo_buyer_id,
                "access_token": "demo-access-token",
                "refresh_token": "demo-refresh-token",
                "device_name": "Demo Device",
                "device_platform": "web",
                "access_token_expires_at": now,
                "refresh_token_expires_at": now,
                "is_new_user": False,
                "revoked_at": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        self._seed(
            "login_attempt",
            "login_attempt_1",
            {
                "id": "login_attempt_1",
                "login_identifier": "demo-buyer",
                "user_id": demo_buyer_id,
                "success": True,
                "failure_reason": None,
                "ip_address": "127.0.0.1",
                "user_agent": "seed",
                "occurred_at": now,
            },
        )

        self._seed(
            "notification",
            "notification_1",
            {
                "id": "notification_1",
                "user_id": demo_buyer_id,
                "notification_type": "order",
                "title": "订单已发货",
                "body": "你的相机订单已经发货。",
                "entity_type": "order",
                "entity_id": order_id,
                "read_at": None,
                "created_at": now,
            },
        )
        self._seed(
            "notification",
            "notification_2",
            {
                "id": "notification_2",
                "user_id": demo_buyer_id,
                "notification_type": "message",
                "title": "卖家回复了你",
                "body": "卖家回复了相机的议价消息。",
                "entity_type": "conversation",
                "entity_id": conversation_id,
                "read_at": None,
                "created_at": now,
            },
        )

        self._seed(
            "search_suggestion",
            "search_demo_1",
            {
                "query": "",
                "suggestions": ["相机", "人体工学椅", "通勤包", "3D 展示"],
                "recent_queries": ["相机", "二手椅子"],
            },
        )

        self.connection.commit()

    def _calculate_age(self, birth_date: str | None) -> int | None:
        if not birth_date:
            return None
        try:
            year = int(birth_date.split("-")[0])
        except (ValueError, AttributeError, IndexError):
            return None
        return max(datetime.now().year - year, 0)

    def default_user_id(self) -> str:
        record = self.find_first("user", predicate=lambda item: item["payload"].get("identifier") == "demo-buyer")
        if record:
            return record["entity_id"]
        first_user = self.find_first("user")
        if first_user:
            return first_user["entity_id"]
        self._seed_if_needed()
        first_user = self.find_first("user")
        if first_user:
            return first_user["entity_id"]
        raise RuntimeError("No seeded user available.")

    def user_record(self, user_id: str) -> dict[str, Any] | None:
        return self.get_record("user", user_id)

    def profile_record(self, user_id: str) -> dict[str, Any] | None:
        return self.get_record("user_profile", user_id)

    def session_by_token(self, access_token: str | None) -> dict[str, Any] | None:
        if not access_token:
            return None
        for record in self.list_records("auth_session"):
            payload = record["payload"]
            if payload.get("access_token") == access_token and not payload.get("revoked_at"):
                return record
        return None

    def user_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        normalized = identifier.strip().lower()
        for record in self.list_records("user"):
            payload = record["payload"]
            candidates = {
                str(payload.get("identifier", "")).lower(),
                str(payload.get("email", "")).lower(),
                str(payload.get("phone", "")).lower(),
                str(payload.get("display_name", "")).lower(),
            }
            if normalized in candidates:
                return record
        return None

    def verify_password(self, user_record: dict[str, Any], password: str) -> bool:
        payload = user_record["payload"]
        return _verify_password_hash(password, payload.get("password_hash"))

    def hash_password(self, password: str) -> str:
        return _hash_password(password)

    def create_session(
        self,
        user_id: str,
        *,
        device_name: str | None = None,
        device_platform: str | None = None,
        is_new_user: bool = False,
    ) -> dict[str, Any]:
        now = _utc_now()
        session_id = _generate_id("session")
        access_token = _generate_id("access")
        refresh_token = _generate_id("refresh")
        session = {
            "id": session_id,
            "user_id": user_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "device_name": device_name,
            "device_platform": device_platform,
            "access_token_expires_at": now,
            "refresh_token_expires_at": now,
            "is_new_user": is_new_user,
            "revoked_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self.upsert_record("auth_session", session_id, session)
        return session

    def revoke_session(self, access_token: str | None = None) -> dict[str, Any] | None:
        session = self.session_by_token(access_token)
        if session is None:
            return None
        payload = session["payload"]
        payload["revoked_at"] = _utc_now()
        payload["updated_at"] = _utc_now()
        self.upsert_record("auth_session", session["entity_id"], payload)
        return self.get_record("auth_session", session["entity_id"])

    def update_user_profile(self, user_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        user = self.user_record(user_id)
        if user is None:
            raise KeyError(user_id)
        user_payload = dict(user["payload"])
        profile = self.profile_record(user_id)
        profile_payload = dict(profile["payload"] if profile else {})

        for key in ("display_name", "avatar_url", "bio", "location"):
            if key in changes and changes[key] is not None:
                user_payload[key] = changes[key]
                profile_payload[key] = changes[key]
        if "birth_date" in changes and changes["birth_date"] is not None:
            user_payload["birth_date"] = changes["birth_date"]
            profile_payload["birth_date"] = changes["birth_date"]
            profile_payload["age_years"] = self._calculate_age(changes["birth_date"])
        if "profile_visibility" in changes and changes["profile_visibility"] is not None:
            user_payload["profile_visibility"] = changes["profile_visibility"]
            profile_payload["profile_visibility"] = changes["profile_visibility"]

        user_payload["updated_at"] = _utc_now()
        profile_payload["updated_at"] = _utc_now()
        self.upsert_record("user", user_id, user_payload)
        self.upsert_record("user_profile", user_id, profile_payload)
        return self.profile_record(user_id) or {"entity_id": user_id, "payload": profile_payload}

    def list_user_addresses(self, user_id: str) -> list[dict[str, Any]]:
        return self.list_records("user_address", parent_id=user_id)

    def get_user_address(self, address_id: str) -> dict[str, Any] | None:
        return self.get_record("user_address", address_id)

    def create_user_address(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        address_id = payload.get("id") or _generate_id("address")
        record = {
            "id": address_id,
            "user_id": user_id,
            "recipient_name": payload.get("recipient_name") or "",
            "phone": payload.get("phone") or "",
            "region_code": payload.get("region_code") or "",
            "address_line1": payload.get("address_line1") or "",
            "address_line2": payload.get("address_line2"),
            "is_default": bool(payload.get("is_default", False)),
            "created_at": now,
            "updated_at": now,
        }
        if record["is_default"]:
            self._clear_default_user_addresses(user_id)
        stored = self.upsert_record("user_address", address_id, record, parent_id=user_id)
        if record["is_default"]:
            self._mark_default_user_address(user_id, address_id)
        return stored

    def update_user_address(self, address_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        address = self.get_user_address(address_id)
        if address is None:
            raise KeyError(address_id)
        payload = dict(address["payload"])
        for key in ("recipient_name", "phone", "region_code", "address_line1", "address_line2"):
            if key in changes and changes[key] is not None:
                payload[key] = changes[key]
        if "is_default" in changes and changes["is_default"] is not None:
            payload["is_default"] = bool(changes["is_default"])
        payload["updated_at"] = _utc_now()
        user_id = payload.get("user_id")
        if payload.get("is_default") and user_id:
            self._clear_default_user_addresses(user_id)
        stored = self.upsert_record("user_address", address_id, payload, parent_id=user_id)
        if payload.get("is_default") and user_id:
            self._mark_default_user_address(user_id, address_id)
        return stored

    def delete_user_address(self, address_id: str) -> None:
        self.delete_record("user_address", address_id)

    def _clear_default_user_addresses(self, user_id: str) -> None:
        for record in self.list_records("user_address", parent_id=user_id):
            payload = dict(record["payload"])
            if payload.get("is_default"):
                payload["is_default"] = False
                payload["updated_at"] = _utc_now()
                self.upsert_record("user_address", record["entity_id"], payload, parent_id=user_id)

    def _mark_default_user_address(self, user_id: str, address_id: str) -> None:
        address = self.get_user_address(address_id)
        if address is None:
            return
        payload = dict(address["payload"])
        payload["is_default"] = True
        payload["updated_at"] = _utc_now()
        self.upsert_record("user_address", address_id, payload, parent_id=user_id)

    def default_user_address(self, user_id: str) -> dict[str, Any] | None:
        for record in self.list_records("user_address", parent_id=user_id):
            if record["payload"].get("is_default"):
                return record
        addresses = self.list_records("user_address", parent_id=user_id)
        return addresses[0] if addresses else None

    def user_stats_payload(self, user_id: str) -> dict[str, Any]:
        posts_count = sum(1 for item in self.list_records("listing") if item["payload"].get("seller_id") == user_id)
        sold_count = sum(1 for item in self.list_records("order") if item["payload"].get("seller_id") == user_id and item["payload"].get("status") in {"delivered", "completed"})
        bought_count = sum(1 for item in self.list_records("order") if item["payload"].get("buyer_id") == user_id)
        liked_count = sum(1 for item in self.list_records("listing_favorite") if item["payload"].get("user_id") == user_id)
        followers_count = sum(1 for item in self.list_records("user_follow") if item["payload"].get("following_user_id") == user_id)
        following_count = sum(1 for item in self.list_records("user_follow") if item["payload"].get("follower_user_id") == user_id)
        profile = self.profile_record(user_id)
        profile_payload = dict(profile["payload"] if profile else {})
        return {
            "user_id": user_id,
            "posts_count": posts_count,
            "sold_count": sold_count,
            "bought_count": bought_count,
            "liked_count": liked_count,
            "followers_count": followers_count,
            "following_count": following_count,
            "positive_rate": profile_payload.get("positive_rate", 1.0),
            "sesame_credit_score": profile_payload.get("sesame_credit_score") or 0,
            "vip_level": profile_payload.get("vip_level") or "none",
        }

    def badge_summary_payload(self, user_id: str) -> dict[str, Any]:
        unread_notifications = sum(1 for item in self.list_records("notification") if item["payload"].get("user_id") == user_id and item["payload"].get("read_at") is None)
        unread_messages = 0
        for member in self.list_records("conversation_member"):
            if member["payload"].get("user_id") == user_id:
                unread_messages += int(member["payload"].get("unread_count") or 0)
        active_orders = sum(1 for item in self.list_records("order") if user_id in {item["payload"].get("buyer_id"), item["payload"].get("seller_id")} and item["payload"].get("status") not in {"completed", "cancelled"})
        draft_listings = sum(1 for item in self.list_records("listing_draft") if item["payload"].get("seller_id") == user_id)
        return {
            "unread_notifications": unread_notifications,
            "unread_messages": unread_messages,
            "active_orders": active_orders,
            "draft_listings": draft_listings,
        }

    def listing_preview_payload(self, listing_id: str) -> dict[str, Any]:
        listing = self.get_record("listing", listing_id)
        payload = dict(listing["payload"] if listing else {})
        cover = payload.get("cover_media_json") if isinstance(payload.get("cover_media_json"), dict) else None
        model_url = payload.get("model_url")
        model_ply_url = payload.get("model_ply_url")
        model_sog_url = payload.get("model_sog_url")
        viewer_url = payload.get("viewer_url")
        is_ready = bool(viewer_url or model_url or model_ply_url or model_sog_url)
        preview_status = payload.get("preview_status") or ("ready" if is_ready else "pending")
        if preview_status in {"ready", "ready_for_view", "published"}:
            preview_status = "ready"
        elif preview_status in {"failed", "error"}:
            preview_status = "failed"
        elif preview_status in {"training", "processing", "masking", "queued"}:
            preview_status = "generating"
        else:
            preview_status = "pending"
        return {
            "preview_status": preview_status,
            "status_message": payload.get("status_message") or payload.get("preview_message") or None,
            "viewer_url": viewer_url,
            "model_url": model_url,
            "model_ply_url": model_ply_url,
            "model_sog_url": model_sog_url,
            "log_url": payload.get("log_url"),
            "cover_media": cover,
            "is_ready": is_ready,
            "placeholder": {
                "title": payload.get("title") or "3D 预览暂未就绪",
                "subtitle": payload.get("subtitle") or "上传视频后可自动生成 3D 模型",
                "badges": list(payload.get("badges_json") or []),
            },
        }

    def public_profile_payload(self, user_id: str) -> dict[str, Any]:
        stats = self.user_stats_payload(user_id)
        profile = self.profile_record(user_id)
        payload = dict(profile["payload"] if profile else {})
        return {
            "stats": stats,
            "profile_visibility": payload.get("profile_visibility") or "public",
            "vip_level": payload.get("vip_level") or "none",
        }

    def public_listing_payload(self, listing_id: str) -> dict[str, Any]:
        return self.listing_preview_payload(listing_id)

    def current_user(self, access_token: str | None) -> dict[str, Any]:
        session = self.session_by_token(access_token)
        if session is None:
            user = self.user_record(self.default_user_id())
        else:
            user = self.user_record(session["payload"]["user_id"])
        if user is None:
            raise RuntimeError("No current user available.")
        return user

    def health_snapshot(self) -> dict[str, Any]:
        seeded_users = self.count_records("user")
        seeded_listings = self.count_records("listing")
        demo_user_id = self.default_user_id()
        return {
            "status": "ok",
            "version": "0.1.0",
            "database_ready": True,
            "demo_user_id": demo_user_id,
            "seeded_users": seeded_users,
            "seeded_listings": seeded_listings,
        }

    def version_snapshot(self) -> dict[str, Any]:
        return {
            "api_version": "v1",
            "build_version": "20260411_01",
            "service_name": "3dv-junk-mart backend",
        }

    def public_config_snapshot(self) -> dict[str, Any]:
        feature_flags = {record["payload"].get("flag_key", "guest_entry_enabled"): bool(record["payload"].get("enabled", False)) for record in self.list_records("feature_flag")}
        return {
            "api_version": "v1",
            "base_currency": "CNY",
            "guest_entry_enabled": feature_flags.get("guest_entry_enabled", True),
            "feature_flags": feature_flags,
            "supported_locales": ["zh-CN", "en-US"],
            "trainer_service_base_url": TRAINER_SERVICE_BASE_URL,
            "trainer_service_public_base_url": TRAINER_SERVICE_PUBLIC_BASE_URL,
        }

    def _row_to_dict(self, entity_type: str, record: dict[str, Any]) -> dict[str, Any]:
        payload = dict(record["payload"])
        payload.setdefault("id", record["entity_id"])
        payload.setdefault("entity_type", entity_type)
        return payload

    def _page(self, page: int, page_size: int, total: int) -> dict[str, int | None]:
        next_cursor = None
        if page * page_size < total:
            next_cursor = str(page + 1)
        return {
            "page": page,
            "page_size": page_size,
            "next_cursor": next_cursor,
            "total": total,
        }

    def paginate(self, items: list[dict[str, Any]], *, page: int = 1, page_size: int = 20) -> tuple[list[dict[str, Any]], dict[str, int | None]]:
        safe_page = max(page, 1)
        safe_page_size = max(page_size, 1)
        total = len(items)
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return items[start:end], self._page(safe_page, safe_page_size, total)

    def search_documents(self) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for record in self.list_records("listing"):
            payload = record["payload"]
            documents.append(
                {
                    "listing_id": record["entity_id"],
                    "title_tokens": str(payload.get("title", "")).lower().split(),
                    "category_id": payload.get("category_id"),
                    "price_minor": int(payload.get("price_minor") or 0),
                    "location_city": payload.get("location_city"),
                    "status": payload.get("status"),
                    "ranking_score": 1.0,
                }
            )
        return documents


@lru_cache(maxsize=1)
def get_store() -> MarketplaceStore:
    return MarketplaceStore()


def reset_store_cache() -> None:
    get_store.cache_clear()

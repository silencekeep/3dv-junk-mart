from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app.main as main_module
import backend.app.routes.reconstructions as reconstructions_module
import shared.task_store as task_store_module
from backend.app.main import app
from backend.app.services.marketplace_store import MarketplaceStore, get_store
from tests.fake_trainer_service import FakeTrainerServiceClient
from shared.task_store import (
    atomic_write_json,
    build_task_record,
    create_task,
    now_iso,
    task_model_dir,
    task_processed_dir,
    task_upload_dir,
)


def _hash_password(password: str) -> str:
    iterations = 200_000
    salt = os.urandom(16)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived_key.hex()}"


class DummyReporter:
    def __init__(self, *args: object, **kwargs: object) -> None:
        return

    def log_event(self, *args: object, **kwargs: object) -> None:
        return

    def log(self, *args: object, **kwargs: object) -> None:
        return


@dataclass
class BackendHarness:
    root: Path
    storage_root: Path
    viewer_root: Path
    store: MarketplaceStore
    trainer_client: FakeTrainerServiceClient
    client: TestClient

    def close(self) -> None:
        try:
            self.client.close()
        finally:
            self.store.close()
            shutil.rmtree(self.root, ignore_errors=True)

    @property
    def demo_buyer_id(self) -> str:
        record = self.store.find_first("user", predicate=lambda item: item["payload"].get("identifier") == "demo-buyer")
        if record is None:
            raise AssertionError("Seeded demo buyer is missing.")
        return record["entity_id"]

    @property
    def demo_seller_id(self) -> str:
        record = self.store.find_first("user", predicate=lambda item: item["payload"].get("identifier") == "demo-seller")
        if record is None:
            raise AssertionError("Seeded demo seller is missing.")
        return record["entity_id"]

    @property
    def demo_support_id(self) -> str:
        record = self.store.find_first("user", predicate=lambda item: item["payload"].get("identifier") == "support@example.com")
        if record is None:
            raise AssertionError("Seeded support user is missing.")
        return record["entity_id"]

    @property
    def demo_access_token(self) -> str:
        session = self.store.session_by_token("demo-access-token")
        if session is None:
            raise AssertionError("Seeded demo session is missing.")
        return str(session["payload"]["access_token"])

    @property
    def demo_refresh_token(self) -> str:
        session = self.store.session_by_token("demo-access-token")
        if session is None:
            raise AssertionError("Seeded demo session is missing.")
        return str(session["payload"]["refresh_token"])

    @property
    def demo_listing_id(self) -> str:
        record = self.store.find_first("listing", predicate=lambda item: item["payload"].get("title") == "Sony Alpha 7C 二手微单")
        if record is None:
            raise AssertionError("Seeded demo listing is missing.")
        return record["entity_id"]

    @property
    def demo_order_id(self) -> str:
        record = self.store.find_first("order", predicate=lambda item: item["payload"].get("buyer_id") == self.demo_buyer_id)
        if record is None:
            raise AssertionError("Seeded demo order is missing.")
        return record["entity_id"]

    @property
    def demo_conversation_id(self) -> str:
        record = self.store.find_first("conversation", predicate=lambda item: item["payload"].get("buyer_id") == self.demo_buyer_id)
        if record is None:
            raise AssertionError("Seeded demo conversation is missing.")
        return record["entity_id"]

    def auth_headers(self, token: str | None, *, style: str = "standard") -> dict[str, str]:
        if token is None:
            return {}
        if style == "none":
            return {}
        if style == "lower":
            return {"authorization": f"bearer {token}"}
        if style == "spaced":
            return {"Authorization": f"Bearer    {token}"}
        if style == "garbage":
            return {"Authorization": token}
        return {"Authorization": f"Bearer {token}"}

    def make_user_session(
        self,
        *,
        identifier: str | None = None,
        password: str = "TempPass123!",
        display_name: str = "Temp User",
        vip_level: str = "none",
        profile_visibility: str = "public",
    ) -> tuple[str, str, str]:
        user_id = f"user_{uuid.uuid4().hex[:10]}"
        identifier_value = identifier or f"temp-{uuid.uuid4().hex[:8]}"
        now = now_iso()
        user_payload = {
            "id": user_id,
            "identifier": identifier_value,
            "password_hash": _hash_password(password),
            "display_name": display_name,
            "avatar_url": None,
            "bio": None,
            "location": "Test City",
            "sesame_credit_score": 650,
            "vip_level": vip_level,
            "profile_visibility": profile_visibility,
            "birth_date": None,
            "status": "active",
            "registered_at": now,
            "last_login_at": now,
            "password_updated_at": now,
            "account_locked_until": None,
            "created_at": now,
            "updated_at": now,
        }
        profile_payload = {
            "id": user_id,
            "display_name": display_name,
            "avatar_url": None,
            "birth_date": None,
            "age_years": None,
            "bio": None,
            "location": "Test City",
            "sesame_credit_score": 650,
            "vip_level": vip_level,
            "profile_visibility": profile_visibility,
            "updated_at": now,
        }
        self.store.upsert_record("user", user_id, user_payload)
        self.store.upsert_record("user_profile", user_id, profile_payload)
        session = self.store.create_session(user_id, device_name="Backend Test Device", device_platform="web", is_new_user=False)
        return user_id, str(session["access_token"]), str(session["refresh_token"])

    def make_listing(
        self,
        *,
        title: str,
        seller_id: str | None = None,
        category_id: str = "cat_home",
        status: str = "live",
        listing_id: str | None = None,
        preview_ready: bool = False,
        preview_status: str | None = None,
    ) -> str:
        seller = seller_id or self.demo_seller_id
        record_id = listing_id or f"listing_{uuid.uuid4().hex[:10]}"
        now = now_iso()
        listing_payload: dict[str, Any] = {
            "id": record_id,
            "seller_id": seller,
            "category_id": category_id,
            "title": title,
            "subtitle": f"{title} subtitle",
            "description": f"{title} description",
            "price_minor": 19900,
            "original_price_minor": 29900,
            "currency": "CNY",
            "status": status,
            "condition_level": "good",
            "location_city": "Test City",
            "cover_media_json": {
                "id": f"media_{record_id}_cover",
                "kind": "image",
                "url": f"/storage/test/{record_id}.jpg",
                "thumbnail_url": f"/storage/test/{record_id}_thumb.jpg",
                "width": 1200,
                "height": 900,
                "mime_type": "image/jpeg",
                "sort_order": 0,
            },
            "badges_json": ["test"],
            "model_url": f"/storage/models/{record_id}/model.ply" if preview_ready else None,
            "model_ply_url": f"/storage/models/{record_id}/model.ply" if preview_ready else None,
            "model_sog_url": f"/storage/models/{record_id}/model.sog" if preview_ready else None,
            "model_format": "ply" if preview_ready else None,
            "viewer_url": f"/viewer/index.html?task_id={record_id}" if preview_ready else None,
            "log_url": f"/storage/models/{record_id}/train.log" if preview_ready else None,
            "remote_task_id": None,
            "object_masking": False,
            "quality_profile": None,
            "published_at": now if status == "live" else None,
            "created_at": now,
            "updated_at": now,
            "preview_status": preview_status,
        }
        self.store.upsert_record("listing", record_id, listing_payload)
        return record_id

    def make_order(
        self,
        *,
        buyer_id: str | None = None,
        seller_id: str | None = None,
        listing_id: str | None = None,
        status: str = "shipped",
        order_id: str | None = None,
        can_confirm_receipt: bool = True,
    ) -> str:
        record_id = order_id or f"order_{uuid.uuid4().hex[:10]}"
        buyer = buyer_id or self.demo_buyer_id
        seller = seller_id or self.demo_seller_id
        listing = listing_id or self.demo_listing_id
        now = now_iso()
        payload = {
            "id": record_id,
            "order_no": f"ORD-{uuid.uuid4().hex[:8].upper()}",
            "buyer_id": buyer,
            "seller_id": seller,
            "listing_id": listing,
            "status": status,
            "payment_status": "paid",
            "shipping_status": "shipped",
            "currency": "CNY",
            "subtotal_minor": 519900,
            "shipping_minor": 0,
            "discount_minor": 10000,
            "total_minor": 509900,
            "can_confirm_receipt": can_confirm_receipt,
            "item_snapshot_json": {
                "listing_id": listing,
                "title": f"{record_id} item",
                "price_minor": 519900,
                "currency": "CNY",
                "cover_asset_id": f"cover_{record_id}",
                "seller_display_name": "Demo Seller",
            },
            "logistics_json": {
                "carrier_name": "顺丰速运",
                "tracking_no": f"SF{uuid.uuid4().hex[:10].upper()}",
                "status": "shipped",
                "shipped_at": now,
                "estimated_delivery_at": now,
                "address": {
                    "receiver_name": "Demo Buyer",
                    "phone": "13800000000",
                    "region": "Test City",
                    "detail": "Demo Road 1",
                },
            },
            "created_at": now,
            "updated_at": now,
        }
        self.store.upsert_record("order", record_id, payload)
        return record_id

    def make_conversation(
        self,
        *,
        buyer_id: str | None = None,
        seller_id: str | None = None,
        listing_id: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        record_id = conversation_id or f"conversation_{uuid.uuid4().hex[:10]}"
        buyer = buyer_id or self.demo_buyer_id
        seller = seller_id or self.demo_seller_id
        listing = listing_id or self.demo_listing_id
        now = now_iso()
        conversation_payload = {
            "id": record_id,
            "listing_id": listing,
            "buyer_id": buyer,
            "seller_id": seller,
            "status": "active",
            "last_message_preview": "测试消息",
            "unread_count": 1,
            "updated_at": now,
            "last_message_at": now,
        }
        self.store.upsert_record("conversation", record_id, conversation_payload)
        self.store.upsert_record(
            "conversation_member",
            f"member_{record_id}_{buyer}",
            {
                "conversation_id": record_id,
                "user_id": buyer,
                "role": "buyer",
                "last_read_message_id": None,
                "unread_count": 0,
            },
            parent_id=record_id,
        )
        self.store.upsert_record(
            "conversation_member",
            f"member_{record_id}_{seller}",
            {
                "conversation_id": record_id,
                "user_id": seller,
                "role": "seller",
                "last_read_message_id": None,
                "unread_count": 1,
            },
            parent_id=record_id,
        )
        self.store.upsert_record(
            "message",
            f"message_{record_id}_1",
            {
                "id": f"message_{record_id}_1",
                "conversation_id": record_id,
                "sender_id": buyer,
                "message_type": "text",
                "content_text": "测试消息",
                "asset": None,
                "created_at": now,
                "read_at": None,
            },
            parent_id=record_id,
        )
        return record_id

    def make_review(self, *, order_id: str | None = None, listing_id: str | None = None) -> str:
        review_id = f"review_{uuid.uuid4().hex[:10]}"
        now = now_iso()
        payload = {
            "id": review_id,
            "order_id": order_id or self.demo_order_id,
            "listing_id": listing_id or self.demo_listing_id,
            "reviewer_user_id": self.demo_buyer_id,
            "seller_user_id": self.demo_seller_id,
            "rating": 5,
            "content": "很好",
            "is_anonymous": False,
            "status": "published",
            "created_at": now,
            "updated_at": now,
        }
        self.store.upsert_record("review", review_id, payload)
        return review_id

    def make_address(self, *, user_id: str | None = None, is_default: bool = False) -> str:
        address_id = f"address_{uuid.uuid4().hex[:10]}"
        self.store.create_user_address(
            user_id or self.demo_buyer_id,
            {
                "id": address_id,
                "recipient_name": "测试收件人",
                "phone": "13800000000",
                "region_code": "310000",
                "address_line1": "测试路 1 号",
                "address_line2": "2 单元 201",
                "is_default": is_default,
            },
        )
        return address_id

    def make_task(
        self,
        *,
        task_id: str | None = None,
        title: str = "Task Title",
        description: str = "Task Description",
        price: str = "99.00",
        status: str = "uploaded",
        quality_profile: str | None = None,
        object_masking: bool = False,
        model_rel_path: str | None = None,
        viewer_config: dict[str, Any] | None = None,
        mask_prompt_frame_name: str | None = None,
        mask_prompt_frame_rel_path: str | None = None,
        mask_prompt_frame_width: int | None = 1920,
        mask_prompt_frame_height: int | None = 1080,
        mock_mode: bool = False,
    ) -> dict[str, Any]:
        record_id = task_id or f"task_{uuid.uuid4().hex[:10]}"
        upload_dir = task_upload_dir(record_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        video_path = upload_dir / "source.mp4"
        video_path.write_bytes(b"video")
        task = build_task_record(
            task_id=record_id,
            title=title,
            description=description,
            price=price,
            source_filename="source.mp4",
            video_path=video_path,
            video_metadata={"streams": [{"codec_type": "video"}], "format": {"duration": 1.0}},
        )
        task.update(
            {
                "status": status,
                "quality_profile": quality_profile,
                "object_masking": object_masking,
                "model_rel_path": model_rel_path,
                "model_ply_rel_path": model_rel_path,
                "model_sog_rel_path": None,
                "model_format": "ply" if model_rel_path else None,
                "mask_prompt_frame_name": mask_prompt_frame_name,
                "mask_prompt_frame_rel_path": mask_prompt_frame_rel_path,
                "mask_prompt_frame_width": mask_prompt_frame_width,
                "mask_prompt_frame_height": mask_prompt_frame_height,
                "mock_mode": mock_mode,
                "remote_task_id": record_id,
            }
        )
        created = create_task(task)
        if viewer_config is not None:
            model_dir = task_model_dir(record_id)
            model_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(model_dir / "viewer.json", viewer_config)
        self.trainer_client.seed_task(created)
        return created

    def prepare_mask_debug_dataset(self, task_id: str) -> None:
        dataset_dir = task_processed_dir(task_id) / "dataset"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        (dataset_dir / "images").mkdir(parents=True, exist_ok=True)
        (dataset_dir / "transforms.json").write_text("{}", encoding="utf-8")

    def prepare_mask_preview_artifacts(self, task_id: str, frame_name: str) -> None:
        processed_dir = task_processed_dir(task_id)
        processed_dir.mkdir(parents=True, exist_ok=True)
        (processed_dir / "mask_prompts.json").write_text("{}", encoding="utf-8")
        (processed_dir / "mask_preview_manifest.json").write_text("{}", encoding="utf-8")
        frame_path = processed_dir / "mask_preview_frames" / f"{Path(frame_name).stem}.jpg"
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        frame_path.write_bytes(b"preview")


@contextmanager
def backend_harness(scope: str) -> Iterator[BackendHarness]:
    root = Path(tempfile.mkdtemp(prefix=f"3dv_{scope}_"))
    storage_root = root / "storage"
    viewer_root = root / "viewer"
    storage_root.mkdir(parents=True, exist_ok=True)
    viewer_root.mkdir(parents=True, exist_ok=True)
    store = MarketplaceStore(db_path=root / "business.db")
    trainer_client = FakeTrainerServiceClient()

    def _override_get_store() -> MarketplaceStore:
        return store

    app.dependency_overrides[get_store] = _override_get_store

    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(main_module, "get_store", lambda: store))
            stack.enter_context(patch.object(reconstructions_module, "STORAGE_ROOT", storage_root))
            stack.enter_context(patch.object(reconstructions_module, "REPO_ROOT", root))
            stack.enter_context(patch.object(reconstructions_module, "PipelineReporter", DummyReporter))
            stack.enter_context(patch.object(reconstructions_module, "get_trainer_service_client", lambda: trainer_client))
            stack.enter_context(patch.object(task_store_module, "STORAGE_ROOT", storage_root))
            stack.enter_context(patch.object(task_store_module, "TASKS_ROOT", storage_root / "tasks"))
            stack.enter_context(patch.object(task_store_module, "UPLOADS_ROOT", storage_root / "uploads"))
            stack.enter_context(patch.object(task_store_module, "PROCESSED_ROOT", storage_root / "processed"))
            stack.enter_context(patch.object(task_store_module, "MODELS_ROOT", storage_root / "models"))
            stack.enter_context(patch.object(task_store_module, "VIEWER_ROOT", viewer_root))
            with TestClient(app) as client:
                yield BackendHarness(
                    root=root,
                    storage_root=storage_root,
                    viewer_root=viewer_root,
                    store=store,
                    trainer_client=trainer_client,
                    client=client,
                )
    finally:
        app.dependency_overrides.pop(get_store, None)
        store.close()
        shutil.rmtree(root, ignore_errors=True)


__all__ = ["BackendHarness", "DummyReporter", "backend_harness"]

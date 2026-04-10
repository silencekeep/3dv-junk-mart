from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import unittest
from unittest.mock import patch

import backend.app.routes.reconstructions as reconstructions_module
from tests.backend_test_support import backend_harness


AUTH_STATES = ["none", "invalid", "standard", "lower", "spaced", "demo", "fresh", "revoked"]


def _assert_success(testcase, response, expected_status: int = 200):
    testcase.assertEqual(response.status_code, expected_status)
    payload = response.json()
    if isinstance(payload, dict) and "code" in payload:
        testcase.assertEqual(payload["code"], 0)
        testcase.assertEqual(payload["message"], "ok")
        testcase.assertIn("meta", payload)
        testcase.assertIn("request_id", payload["meta"])
        testcase.assertIsInstance(payload["meta"]["request_id"], str)
        return payload.get("data"), payload
    return payload, payload


def _assert_error(testcase, response, expected_status: int, expected_code: int):
    testcase.assertEqual(response.status_code, expected_status)
    payload = response.json()
    testcase.assertEqual(payload["code"], expected_code)
    testcase.assertNotEqual(payload["code"], 0)
    testcase.assertIn("meta", payload)
    testcase.assertIn("request_id", payload["meta"])
    testcase.assertIsInstance(payload["meta"]["request_id"], str)
    return payload


def _headers_for_state(
    harness,
    state: str,
    fresh_token: str,
    revoked_token: str,
    *,
    prefer_fresh_valid: bool = False,
) -> dict[str, str]:
    if state == "none":
        return {}
    if state == "invalid":
        return {"Authorization": "Bearer invalid-token"}

    if state == "revoked":
        token = revoked_token
    elif state == "fresh":
        token = fresh_token
    else:
        token = harness.demo_access_token

    if state == "lower":
        return {"authorization": f"bearer {token}"}
    if state == "spaced":
        return {"Authorization": f"Bearer    {token}"}
    if state == "garbage":
        return {"Authorization": "Token invalid"}
    return {"Authorization": f"Bearer {token}"}


def _make_matrix_tokens(harness):
    fresh_user_id, fresh_token, _ = harness.make_user_session(identifier=f"fresh-{uuid.uuid4().hex[:8]}")
    _, revoked_token, _ = harness.make_user_session(identifier=f"revoked-{uuid.uuid4().hex[:8]}")
    harness.store.revoke_session(revoked_token)
    _, logout_token, logout_refresh = harness.make_user_session(identifier=f"logout-{uuid.uuid4().hex[:8]}")
    _, refresh_token, refresh_refresh = harness.make_user_session(identifier=f"refresh-{uuid.uuid4().hex[:8]}")
    return {
        "fresh_user_id": fresh_user_id,
        "fresh": fresh_token,
        "revoked": revoked_token,
        "logout": logout_token,
        "refresh": refresh_token,
        "logout_refresh": logout_refresh,
        "refresh_refresh": refresh_refresh,
    }


class BackendMatrixTestCase(unittest.TestCase):
    def test_marketplace_public_matrix(self) -> None:
        families = [
            "core",
            "catalog",
            "pages",
            "search",
            "listings",
            "listing_detail",
            "users",
            "auth",
        ]

        with backend_harness("marketplace_public") as harness:
            tokens = _make_matrix_tokens(harness)
            case_count = 0

            for family in families:
                for state in AUTH_STATES:
                    for mode in range(8):
                        case_count += 1
                        with self.subTest(family=family, state=state, mode=mode):
                            headers = _headers_for_state(
                                harness,
                                state,
                                tokens["fresh"],
                                tokens["revoked"],
                            )
                            client = harness.client

                            if family == "core":
                                route = mode % 3
                                if route == 0:
                                    response = client.get("/health", headers=headers)
                                    self.assertEqual(response.status_code, 200)
                                    data = response.json()
                                    self.assertEqual(data["status"], "ok")
                                    self.assertGreaterEqual(data["seeded_users"], 3)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/version", headers=headers))
                                    self.assertEqual(data["api_version"], "v1")
                                    self.assertIn("service_name", data)
                                else:
                                    data, _ = _assert_success(self, client.get("/api/v1/config/public", headers=headers))
                                    self.assertEqual(data["base_currency"], "CNY")
                                    self.assertIsInstance(data["supported_locales"], list)
                                    self.assertIn("guest_entry_enabled", data)

                            elif family == "catalog":
                                route = mode % 3
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/categories", headers=headers))
                                    self.assertIsInstance(data, list)
                                    self.assertGreaterEqual(len(data), 1)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/service-catalog", headers=headers))
                                    self.assertIsInstance(data, list)
                                    self.assertGreaterEqual(len(data), 1)
                                else:
                                    data, _ = _assert_success(self, client.get("/api/v1/banners", headers=headers))
                                    self.assertIsInstance(data, list)
                                    self.assertGreaterEqual(len(data), 1)

                            elif family == "pages":
                                route = mode % 4
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/pages/home", headers=headers))
                                    self.assertEqual(data["page_key"], "home")
                                    self.assertIn("resources", data)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/pages/search", headers=headers))
                                    self.assertEqual(data["page_key"], "search")
                                    self.assertIn("resources", data)
                                elif route == 2:
                                    data, _ = _assert_success(self, client.get("/api/v1/pages/auth/login", headers=headers))
                                    self.assertEqual(data["page_key"], "auth_login")
                                else:
                                    data, _ = _assert_success(self, client.get("/api/v1/pages/auth/register", headers=headers))
                                    self.assertEqual(data["page_key"], "auth_register")

                            elif family == "search":
                                route = mode % 4
                                if route == 0:
                                    query = ["", "相机", "3D", "不存在", "  相机  ", "A" * 128, "demo", "二手"]
                                    data, _ = _assert_success(
                                        self,
                                        client.get("/api/v1/search/suggestions", params={"query": query[mode]}, headers=headers),
                                    )
                                    self.assertEqual(data["query"], query[mode])
                                    self.assertIsInstance(data["suggestions"], list)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/search/facets", headers=headers))
                                    self.assertIn("categories", data)
                                    self.assertIn("price_buckets", data)
                                elif route == 2:
                                    data, _ = _assert_success(
                                        self,
                                        client.get("/api/v1/search/suggestions", params={"query": "相机"}, headers=headers),
                                    )
                                    self.assertTrue(data["suggestions"])
                                else:
                                    data, _ = _assert_success(
                                        self,
                                        client.get("/api/v1/search/suggestions", params={"query": ""}, headers=headers),
                                    )
                                    self.assertIsInstance(data["recent_queries"], list)

                            elif family == "listings":
                                route = mode % 4
                                if route == 0:
                                    data, payload = _assert_success(
                                        self,
                                        client.get("/api/v1/listings", params={"page": 1, "page_size": 20}, headers=headers),
                                    )
                                    self.assertIsInstance(data, list)
                                    self.assertIn("page", payload["meta"])
                                elif route == 1:
                                    data, _ = _assert_success(
                                        self,
                                        client.get("/api/v1/listings", params={"status": "live", "page_size": 1}, headers=headers),
                                    )
                                    self.assertLessEqual(len(data), 1)
                                elif route == 2:
                                    data, _ = _assert_success(
                                        self,
                                        client.get("/api/v1/categories/cat_home/listings", params={"page_size": 100}, headers=headers),
                                    )
                                    self.assertIsInstance(data, list)
                                else:
                                    response = client.get("/api/v1/listings", params={"page_size": 0}, headers=headers)
                                    _assert_error(self, response, 422, 2001)

                            elif family == "listing_detail":
                                valid_listing_id = harness.demo_listing_id
                                missing_listing_id = f"listing_missing_{mode}"
                                route = mode % 6
                                if route == 0:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/pages/listings/{valid_listing_id}", headers=headers))
                                    self.assertEqual(data["page_key"], "listing_detail")
                                    self.assertIn("preview_3d", data["resources"])
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/listings/{valid_listing_id}", headers=headers))
                                    self.assertEqual(data["listing"]["id"], valid_listing_id)
                                    self.assertIn("preview_3d", data)
                                elif route == 2:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/listings/{valid_listing_id}/media", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif route == 3:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/listings/{valid_listing_id}/seller", headers=headers))
                                    self.assertEqual(data["id"], harness.demo_seller_id)
                                elif route == 4:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/listings/{valid_listing_id}/specs", headers=headers))
                                    self.assertIsInstance(data, list)
                                else:
                                    response = client.get(f"/api/v1/listings/{missing_listing_id}", headers=headers)
                                    _assert_error(self, response, 404, 3004)

                            elif family == "users":
                                valid_user_id = harness.demo_buyer_id if mode % 2 == 0 else harness.demo_seller_id
                                missing_user_id = f"user_missing_{mode}"
                                route = mode % 4
                                if route == 0:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/users/{valid_user_id}", headers=headers))
                                    self.assertEqual(data["id"], valid_user_id)
                                elif route == 1:
                                    response = client.get(f"/api/v1/users/{missing_user_id}", headers=headers)
                                    _assert_error(self, response, 404, 3004)
                                elif route == 2:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/users/{valid_user_id}/followers", headers=headers))
                                    self.assertIsInstance(data, list)
                                else:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/users/{valid_user_id}/following", headers=headers))
                                    self.assertIsInstance(data, list)

                            else:
                                route = mode % 8
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/auth/session", headers=headers))
                                    self.assertIn("user", data)
                                    if state == "fresh":
                                        self.assertEqual(data["user"]["id"], tokens["fresh_user_id"])
                                    else:
                                        self.assertEqual(data["user"]["id"], harness.demo_buyer_id)
                                elif route == 1:
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            "/api/v1/auth/login",
                                            json={"identifier": "demo-buyer", "password": "demo12345", "device_name": "Matrix"},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertIn("session", data)
                                elif route == 2:
                                    response = client.post(
                                        "/api/v1/auth/login",
                                        json={"identifier": "demo-buyer", "password": "wrong-password"},
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 401, 1001)
                                elif route == 3:
                                    identifier = f"register-{mode}-{state}-{uuid.uuid4().hex[:8]}"
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            "/api/v1/auth/register",
                                            json={
                                                "display_name": f"Matrix {mode}",
                                                "identifier": identifier,
                                                "password": "MatrixPass123!",
                                                "consent_version": "v1",
                                            },
                                            headers=headers,
                                        ),
                                    )
                                    self.assertIn("session", data)
                                elif route == 4:
                                    identifier = f"register-duplicate-{mode}-{uuid.uuid4().hex[:8]}"
                                    first = client.post(
                                        "/api/v1/auth/register",
                                        json={
                                            "display_name": f"Matrix Duplicate {mode}",
                                            "identifier": identifier,
                                            "password": "MatrixPass123!",
                                            "consent_version": "v1",
                                        },
                                        headers=headers,
                                    )
                                    _assert_success(self, first)
                                    response = client.post(
                                        "/api/v1/auth/register",
                                        json={
                                            "display_name": f"Matrix Duplicate {mode}",
                                            "identifier": identifier,
                                            "password": "MatrixPass123!",
                                            "consent_version": "v1",
                                        },
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 409, 3002)
                                elif route == 5:
                                    _, refresh_access, refresh_refresh = harness.make_user_session(
                                        identifier=f"refresh-case-{mode}-{state}-{uuid.uuid4().hex[:8]}"
                                    )
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            "/api/v1/auth/refresh",
                                            json={"refresh_token": refresh_refresh},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertIn("session", data)
                                elif route == 6:
                                    response = client.post(
                                        "/api/v1/auth/refresh",
                                        json={"refresh_token": f"refresh-missing-{mode}"},
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 401, 1001)
                                else:
                                    _, logout_access, _ = harness.make_user_session(
                                        identifier=f"logout-case-{mode}-{state}-{uuid.uuid4().hex[:8]}"
                                    )
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            "/api/v1/auth/logout",
                                            json={"access_token": logout_access},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertTrue(data["revoked"])

            self.assertEqual(case_count, 512)

    def test_marketplace_private_matrix(self) -> None:
        families = [
            "profile",
            "addresses",
            "uploads",
            "wallet_membership",
            "notifications",
            "listings_and_drafts",
            "conversations",
            "orders",
        ]

        with backend_harness("marketplace_private") as harness:
            tokens = _make_matrix_tokens(harness)
            fresh_user_id = tokens["fresh_user_id"]
            case_count = 0

            for family in families:
                for state in AUTH_STATES:
                    for mode in range(8):
                        case_count += 1
                        with self.subTest(family=family, state=state, mode=mode):
                            prefer_fresh_valid = mode in {1, 2, 4, 5, 6, 7}
                            headers = _headers_for_state(
                                harness,
                                state,
                                tokens["fresh"],
                                tokens["revoked"],
                                prefer_fresh_valid=prefer_fresh_valid,
                            )
                            client = harness.client
                            valid_state = state not in {"none", "invalid", "revoked", "garbage"}

                            if not valid_state:
                                if family == "uploads" and mode in {0, 1, 2, 6, 7}:
                                    response = client.post(
                                        "/api/v1/uploads/presign",
                                        json={"filename": "clip.mp4", "kind": "image"},
                                        headers=headers,
                                    )
                                elif family == "profile" and mode in {1, 2}:
                                    response = client.patch(
                                        "/api/v1/users/me",
                                        json={"display_name": "Denied", "profile_visibility": "public"},
                                        headers=headers,
                                    )
                                elif family == "addresses" and mode in {1, 2, 3, 4, 5, 6, 7}:
                                    response = client.post(
                                        "/api/v1/users/me/addresses",
                                        json={
                                            "recipient_name": "Denied",
                                            "phone": "13800000000",
                                            "region_code": "310000",
                                            "address_line1": "Denied",
                                        },
                                        headers=headers,
                                    )
                                elif family == "wallet_membership":
                                    response = client.get("/api/v1/wallet", headers=headers)
                                else:
                                    response = client.get("/api/v1/users/me", headers=headers)
                                _assert_error(self, response, 401, 1001)
                                continue

                            current_user_id = fresh_user_id if state == "fresh" else harness.demo_buyer_id

                            if family == "profile":
                                route = mode % 8
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/users/me", headers=headers))
                                    self.assertEqual(data["id"], current_user_id)
                                elif route == 1:
                                    data, _ = _assert_success(
                                        self,
                                        client.patch(
                                            "/api/v1/users/me",
                                            json={
                                                "display_name": f"Profile {mode}",
                                                "location": "Matrix City",
                                                "profile_visibility": "friends",
                                            },
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["profile_visibility"], "friends")
                                elif route == 2:
                                    response = client.patch(
                                        "/api/v1/users/me",
                                        json={"display_name": "Broken", "profile_visibility": "invalid"},
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 422, 2001)
                                elif route == 3:
                                    data, _ = _assert_success(self, client.get("/api/v1/users/me/stats", headers=headers))
                                    self.assertIn("posts_count", data)
                                elif route == 4:
                                    data, _ = _assert_success(self, client.get("/api/v1/pages/me", headers=headers))
                                    self.assertEqual(data["page_key"], "me")
                                elif route == 5:
                                    data, _ = _assert_success(self, client.get("/api/v1/pages/me/settings", headers=headers))
                                    self.assertEqual(data["page_key"], "me_settings")
                                elif route == 6:
                                    data, payload = _assert_success(self, client.get("/api/v1/users/me/listings", params={"page": 1, "page_size": 1}, headers=headers))
                                    self.assertIsInstance(data, list)
                                    self.assertEqual(payload["meta"]["page"]["page_size"], 1)
                                else:
                                    response = client.get("/api/v1/users/me/favorites", params={"page_size": 0}, headers=headers)
                                    _assert_error(self, response, 422, 2001)

                            elif family == "addresses":
                                user_id = current_user_id
                                route = mode % 8
                                address_id = harness.make_address(user_id=user_id, is_default=route in {1, 3})
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/users/me/addresses", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif route == 1:
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            "/api/v1/users/me/addresses",
                                            json={
                                                "recipient_name": f"Receiver {mode}",
                                                "phone": "13800000000",
                                                "region_code": "310000",
                                                "address_line1": "Matrix Road 1",
                                                "address_line2": "Room 101",
                                                "is_default": True,
                                            },
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["recipient_name"], f"Receiver {mode}")
                                elif route == 2:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/users/me/addresses/{address_id}", headers=headers))
                                    self.assertEqual(data["id"], address_id)
                                elif route == 3:
                                    data, _ = _assert_success(
                                        self,
                                        client.patch(
                                            f"/api/v1/users/me/addresses/{address_id}",
                                            json={"recipient_name": f"Updated {mode}", "is_default": True},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["recipient_name"], f"Updated {mode}")
                                elif route == 4:
                                    data, _ = _assert_success(self, client.delete(f"/api/v1/users/me/addresses/{address_id}", headers=headers))
                                    self.assertTrue(data["deleted"])
                                elif route == 5:
                                    client.delete(f"/api/v1/users/me/addresses/{address_id}", headers=headers)
                                    response = client.get(f"/api/v1/users/me/addresses/{address_id}", headers=headers)
                                    _assert_error(self, response, 404, 3004)
                                elif route == 6:
                                    response = client.post(
                                        "/api/v1/users/me/addresses",
                                        json={"recipient_name": "Broken"},
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 422, 2001)
                                else:
                                    response = client.patch(
                                        "/api/v1/users/me/addresses/address_missing",
                                        json={"recipient_name": "Missing"},
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 404, 3004)

                            elif family == "uploads":
                                route = mode % 4
                                payload = {"filename": f"clip-{mode}.mp4", "kind": "image"}
                                if route == 0:
                                    data, _ = _assert_success(self, client.post("/api/v1/uploads/presign", json=payload, headers=headers))
                                    self.assertIn("upload_url", data)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.post("/api/v1/uploads/presign", json={"filename": "clip.mp4", "kind": "video"}, headers=headers))
                                    self.assertEqual(data["method"], "PUT")
                                    self.assertIn("public_url", data)
                                elif route == 2:
                                    response = client.post("/api/v1/uploads/presign", json={"filename": "clip.mp4", "kind": "unknown"}, headers=headers)
                                    _assert_error(self, response, 422, 2001)
                                else:
                                    data, _ = _assert_success(self, client.post("/api/v1/uploads/presign", json={"filename": "x" * 64, "kind": "document"}, headers=headers))
                                    self.assertTrue(data["upload_url"].startswith("/storage/uploads/"))

                            elif family == "wallet_membership":
                                route = mode % 8
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/wallet", headers=headers))
                                    self.assertIn("account", data)
                                    self.assertIn("transactions", data)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/wallet/transactions", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif route == 2:
                                    data, _ = _assert_success(self, client.get("/api/v1/membership/plans", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif route == 3:
                                    data, _ = _assert_success(self, client.get("/api/v1/membership/subscription", headers=headers))
                                    self.assertTrue(data is None or "plan" in data)
                                elif route == 4:
                                    data, _ = _assert_success(self, client.post("/api/v1/membership/upgrade", json={"plan_key": "gold"}, headers=headers))
                                    self.assertEqual(data["status"], "active")
                                elif route == 5:
                                    response = client.post("/api/v1/membership/upgrade", json={"plan_key": "missing-plan"}, headers=headers)
                                    _assert_error(self, response, 404, 3004)
                                elif route == 6:
                                    data, _ = _assert_success(self, client.get("/api/v1/wallet", headers=headers))
                                    self.assertIn("account", data)
                                else:
                                    data, _ = _assert_success(self, client.get("/api/v1/membership/subscription", headers=headers))
                                    self.assertTrue(data is None or "plan" in data)

                            elif family == "notifications":
                                route = mode % 8
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/notifications", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/badges/summary", headers=headers))
                                    self.assertIn("unread_notifications", data)
                                elif route == 2:
                                    data, _ = _assert_success(self, client.get("/api/v1/notifications/badge", headers=headers))
                                    self.assertIn("draft_listings", data)
                                elif route == 3:
                                    data, _ = _assert_success(
                                        self,
                                        client.post("/api/v1/notifications/read", json={"read_at": None}, headers=headers),
                                    )
                                    self.assertIn("read_count", data)
                                elif route == 4:
                                    notification_id = f"notification_{uuid.uuid4().hex[:10]}"
                                    harness.store.upsert_record(
                                        "notification",
                                        notification_id,
                                        {
                                            "id": notification_id,
                                            "user_id": current_user_id,
                                            "notification_type": "system",
                                            "title": f"Notice {mode}",
                                            "body": "Matrix notification",
                                            "entity_type": "order",
                                            "entity_id": harness.demo_order_id,
                                            "read_at": None,
                                            "created_at": "2026-04-10T00:00:00Z",
                                        },
                                    )
                                    data, _ = _assert_success(
                                        self,
                                        client.patch(f"/api/v1/notifications/{notification_id}/read", json={}, headers=headers),
                                    )
                                    self.assertEqual(data["id"], notification_id)
                                elif route == 5:
                                    response = client.patch("/api/v1/notifications/notification_missing/read", json={}, headers=headers)
                                    _assert_error(self, response, 404, 3004)
                                elif route == 6:
                                    data, _ = _assert_success(self, client.post("/api/v1/notifications/read", json={"read_at": "2024-01-01T00:00:00Z"}, headers=headers))
                                    self.assertIn("read_at", data)
                                else:
                                    response = client.get("/api/v1/notifications", params={"page_size": 0}, headers=headers)
                                    _assert_error(self, response, 422, 2001)

                            elif family == "listings_and_drafts":
                                route = mode % 8
                                listing_id = harness.demo_listing_id if route in {0, 1} else harness.make_listing(title=f"Matrix listing {mode}", seller_id=current_user_id)
                                if route == 0:
                                    data, _ = _assert_success(self, client.post(f"/api/v1/listings/{listing_id}/favorite", headers=headers))
                                    self.assertTrue(data["favorite"])
                                elif route == 1:
                                    data, _ = _assert_success(self, client.delete(f"/api/v1/listings/{listing_id}/favorite", headers=headers))
                                    self.assertFalse(data["favorite"])
                                elif route == 2:
                                    draft_response = client.post(
                                        "/api/v1/listings/drafts",
                                        json={
                                            "title": f"Draft {mode}",
                                            "subtitle": "Draft subtitle",
                                            "description": "Draft description",
                                            "category_id": "cat_home",
                                            "price_minor": 19900,
                                            "original_price_minor": 29900,
                                            "currency": "CNY",
                                            "condition_level": "good",
                                            "location_city": "Test City",
                                            "draft_payload_json": {"mode": mode},
                                        },
                                        headers=headers,
                                    )
                                    data, _ = _assert_success(self, draft_response)
                                    self.assertEqual(data["status"], "draft")
                                elif route == 3:
                                    draft_response = client.post(
                                        "/api/v1/listings/drafts",
                                        json={
                                            "title": f"Draft {mode}",
                                            "description": "Draft description",
                                            "category_id": "cat_home",
                                            "price_minor": 19900,
                                        },
                                        headers=headers,
                                    )
                                    draft_payload, _ = _assert_success(self, draft_response)
                                    draft_id = draft_payload["id"]
                                    data, _ = _assert_success(self, client.get(f"/api/v1/listings/drafts/{draft_id}", headers=headers))
                                    self.assertEqual(data["id"], draft_id)
                                elif route == 4:
                                    draft_response = client.post(
                                        "/api/v1/listings/drafts",
                                        json={"title": f"Draft {mode}", "price_minor": 19900},
                                        headers=headers,
                                    )
                                    draft_payload, _ = _assert_success(self, draft_response)
                                    draft_id = draft_payload["id"]
                                    data, _ = _assert_success(
                                        self,
                                        client.patch(
                                            f"/api/v1/listings/drafts/{draft_id}",
                                            json={"title": f"Updated Draft {mode}", "location_city": "Updated City"},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["title"], f"Updated Draft {mode}")
                                elif route == 5:
                                    draft_response = client.post(
                                        "/api/v1/listings/drafts",
                                        json={"title": f"Publish Draft {mode}", "price_minor": 19900},
                                        headers=headers,
                                    )
                                    draft_payload, _ = _assert_success(self, draft_response)
                                    data, _ = _assert_success(self, client.post(f"/api/v1/listings/drafts/{draft_payload['id']}/publish", headers=headers))
                                    self.assertEqual(data["status"], "live")
                                elif route == 6:
                                    response = client.get("/api/v1/listings/drafts/draft_missing", headers=headers)
                                    _assert_error(self, response, 404, 3004)
                                else:
                                    response = client.post(
                                        "/api/v1/listings/drafts",
                                        json={"title": 123, "price_minor": "broken"},
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 422, 2001)

                            elif family == "conversations":
                                route = mode % 8
                                if state == "fresh":
                                    conversation_id = harness.make_conversation(buyer_id=current_user_id, seller_id=harness.demo_seller_id, listing_id=harness.demo_listing_id)
                                else:
                                    conversation_id = harness.demo_conversation_id
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/conversations", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/conversations/{conversation_id}", headers=headers))
                                    self.assertEqual(data["conversation"]["id"], conversation_id)
                                elif route == 2:
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            f"/api/v1/conversations/{conversation_id}/messages",
                                            json={"content_text": f"Hello {mode}", "message_type": "text"},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["conversation_id"], conversation_id)
                                elif route == 3:
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            f"/api/v1/conversations/{conversation_id}/read",
                                            json={"last_read_message_id": f"message_{mode}"},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["conversation_id"], conversation_id)
                                elif route == 4:
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            f"/api/v1/conversations/{conversation_id}/typing",
                                            json={"is_typing": True},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertTrue(data["is_typing"])
                                elif route == 5:
                                    response = client.get("/api/v1/conversations/conversation_missing", headers=headers)
                                    _assert_error(self, response, 404, 3004)
                                elif route == 6:
                                    response = client.post(
                                        f"/api/v1/conversations/{conversation_id}/messages",
                                        json={"content_text": "bad", "message_type": "broken"},
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 422, 2001)
                                else:
                                    response = client.get("/api/v1/conversations", params={"page_size": 0}, headers=headers)
                                    _assert_error(self, response, 422, 2001)

                            else:
                                route = mode % 8
                                if state == "fresh":
                                    order_id = harness.make_order(buyer_id=current_user_id, seller_id=harness.demo_seller_id, listing_id=harness.demo_listing_id, status="shipped")
                                else:
                                    order_id = harness.demo_order_id
                                if route == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/orders", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif route == 1:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/orders/{order_id}", headers=headers))
                                    self.assertEqual(data["order"]["id"], order_id)
                                elif route == 2:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/orders/{order_id}/timeline", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif route == 3:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/orders/{order_id}/shipment", headers=headers))
                                    self.assertIn("carrier_name", data)
                                elif route == 4:
                                    data, _ = _assert_success(self, client.post(f"/api/v1/orders/{order_id}/confirm-receipt", headers=headers))
                                    self.assertEqual(data["order"]["status"], "completed")
                                elif route == 5:
                                    data, _ = _assert_success(self, client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers))
                                    self.assertEqual(data["order"]["status"], "cancelled")
                                elif route == 6:
                                    response = client.get("/api/v1/orders/order_missing", headers=headers)
                                    _assert_error(self, response, 404, 3004)
                                else:
                                    response = client.post("/api/v1/orders/order_missing/confirm-receipt", headers=headers)
                                    _assert_error(self, response, 404, 3004)

            self.assertEqual(case_count, 512)

    def test_marketplace_store_matrix(self) -> None:
        families = [
            "paginate",
            "records",
            "identity",
            "addresses",
            "stats",
            "preview",
            "public",
            "search",
        ]

        with backend_harness("marketplace_store") as harness:
            case_count = 0

            for family in families:
                for variant in range(8):
                    for mode in range(8):
                        case_count += 1
                        with self.subTest(family=family, variant=variant, mode=mode):
                            if family == "paginate":
                                items = [{"id": f"item_{index}"} for index in range(variant + mode)]
                                page = variant - 2 if mode % 2 == 0 else variant + 1
                                page_size = mode - 1 if variant % 2 == 0 else mode + 1
                                page_items, meta = harness.store.paginate(items, page=page, page_size=page_size)
                                self.assertEqual(meta["page"], max(page, 1))
                                self.assertEqual(meta["page_size"], max(page_size, 1))
                                self.assertLessEqual(len(page_items), max(page_size, 1))
                                self.assertEqual(meta["total"], len(items))

                            elif family == "records":
                                entity_type = f"matrix_record_{variant}"
                                entity_id = f"record_{mode}_{uuid.uuid4().hex[:8]}"
                                payload = {"id": entity_id, "value": mode, "variant": variant}
                                stored = harness.store.upsert_record(entity_type, entity_id, payload)
                                self.assertEqual(stored["entity_id"], entity_id)
                                fetched = harness.store.get_record(entity_type, entity_id)
                                self.assertIsNotNone(fetched)
                                harness.store.delete_record(entity_type, entity_id)
                                self.assertIsNone(harness.store.get_record(entity_type, entity_id))

                            elif family == "identity":
                                identifier = f"identity-{variant}-{mode}-{uuid.uuid4().hex[:8]}"
                                user_id, access_token, refresh_token = harness.make_user_session(identifier=identifier)
                                session = harness.store.session_by_token(access_token)
                                self.assertIsNotNone(session)
                                self.assertEqual(harness.store.user_by_identifier(identifier)["entity_id"], user_id)
                                self.assertTrue(harness.store.verify_password(harness.store.user_record(user_id), "TempPass123!"))
                                revoked = harness.store.revoke_session(access_token)
                                self.assertIsNotNone(revoked)
                                self.assertIsNone(harness.store.session_by_token(access_token))
                                current_user = harness.store.current_user(refresh_token)
                                self.assertIsNotNone(current_user)

                            elif family == "addresses":
                                user_id, _, _ = harness.make_user_session(identifier=f"address-user-{variant}-{mode}-{uuid.uuid4().hex[:4]}")
                                address_id = harness.make_address(user_id=user_id, is_default=mode % 2 == 0)
                                current = harness.store.get_user_address(address_id)
                                self.assertIsNotNone(current)
                                updated = harness.store.update_user_address(address_id, {"recipient_name": f"Updated {variant}", "is_default": True})
                                self.assertTrue(updated["payload"]["is_default"])
                                self.assertEqual(harness.store.default_user_address(user_id)["entity_id"], address_id)
                                harness.store.delete_user_address(address_id)
                                self.assertIsNone(harness.store.get_user_address(address_id))

                            elif family == "stats":
                                user_id = harness.demo_buyer_id if mode % 2 == 0 else harness.demo_seller_id
                                harness.make_listing(title=f"Stats Listing {variant}-{mode}", seller_id=user_id)
                                harness.make_order(buyer_id=user_id, seller_id=harness.demo_seller_id, listing_id=harness.demo_listing_id, status="completed")
                                harness.make_order(buyer_id=harness.demo_buyer_id, seller_id=user_id, listing_id=harness.demo_listing_id, status="shipped")
                                harness.store.upsert_record(
                                    "listing_favorite",
                                    f"favorite_{user_id}_{variant}_{mode}",
                                    {"user_id": user_id, "listing_id": harness.demo_listing_id, "created_at": "now"},
                                    parent_id=harness.demo_listing_id,
                                )
                                stats = harness.store.user_stats_payload(user_id)
                                badge = harness.store.badge_summary_payload(user_id)
                                self.assertEqual(stats["user_id"], user_id)
                                self.assertGreaterEqual(stats["posts_count"], 1)
                                self.assertIn("unread_notifications", badge)

                            elif family == "preview":
                                listing_id = f"preview_{variant}_{mode}_{uuid.uuid4().hex[:6]}"
                                ready = mode % 2 == 0
                                preview_status = ["ready", "failed", "generating", "pending"][mode % 4]
                                harness.make_listing(title=f"Preview {variant}-{mode}", listing_id=listing_id, preview_ready=ready, preview_status=preview_status)
                                preview = harness.store.listing_preview_payload(listing_id)
                                self.assertIn("placeholder", preview)
                                self.assertIn(preview["preview_status"], {"ready", "failed", "generating", "pending"})
                                if ready:
                                    self.assertTrue(preview["is_ready"])

                            elif family == "public":
                                user_id = harness.demo_buyer_id if mode % 2 == 0 else harness.demo_seller_id
                                listing_id = harness.demo_listing_id
                                profile = harness.store.public_profile_payload(user_id)
                                listing = harness.store.public_listing_payload(listing_id)
                                health = harness.store.health_snapshot()
                                version = harness.store.version_snapshot()
                                config = harness.store.public_config_snapshot()
                                self.assertIn("stats", profile)
                                self.assertIn("preview_status", listing)
                                self.assertEqual(health["status"], "ok")
                                self.assertEqual(version["api_version"], "v1")
                                self.assertIn("supported_locales", config)

                            else:
                                documents = harness.store.search_documents()
                                self.assertGreaterEqual(len(documents), 1)
                                default_user_id = harness.store.default_user_id()
                                self.assertIsInstance(default_user_id, str)
                                categories = harness.store.list_records("category")
                                self.assertGreaterEqual(len(categories), 1)

            self.assertEqual(case_count, 512)

    def test_marketplace_commerce_matrix(self) -> None:
        families = [
            "favorites",
            "drafts",
            "conversations",
            "orders",
            "reviews",
            "wallet",
            "membership",
            "notifications",
        ]

        with backend_harness("marketplace_commerce") as harness:
            tokens = _make_matrix_tokens(harness)
            fresh_user_id = tokens["fresh_user_id"]
            case_count = 0

            for family in families:
                for state in AUTH_STATES:
                    for mode in range(8):
                        case_count += 1
                        with self.subTest(family=family, state=state, mode=mode):
                            prefer_fresh_valid = True
                            headers = _headers_for_state(
                                harness,
                                state,
                                tokens["fresh"],
                                tokens["revoked"],
                                prefer_fresh_valid=prefer_fresh_valid,
                            )
                            client = harness.client
                            valid_state = state not in {"none", "invalid", "revoked", "garbage"}
                            current_user_id = fresh_user_id if state == "fresh" else harness.demo_buyer_id

                            if not valid_state:
                                if family == "orders" and mode in {0, 1, 2, 3, 4, 5}:
                                    response = client.get("/api/v1/orders", headers=headers)
                                elif family == "conversations" and mode in {0, 1, 2, 3, 4}:
                                    response = client.get("/api/v1/conversations", headers=headers)
                                elif family == "reviews" and mode in {0, 1, 2, 3, 4, 5, 6, 7}:
                                    response = client.get("/api/v1/wallet", headers=headers)
                                else:
                                    response = client.get("/api/v1/wallet", headers=headers)
                                _assert_error(self, response, 401, 1001)
                                continue

                            if family == "favorites":
                                listing_id = harness.make_listing(title=f"Fav {mode}", seller_id=current_user_id, status="live")
                                if mode % 2 == 0:
                                    data, _ = _assert_success(self, client.post(f"/api/v1/listings/{listing_id}/favorite", headers=headers))
                                    self.assertTrue(data["favorite"])
                                else:
                                    client.post(f"/api/v1/listings/{listing_id}/favorite", headers=headers)
                                    data, _ = _assert_success(self, client.delete(f"/api/v1/listings/{listing_id}/favorite", headers=headers))
                                    self.assertFalse(data["favorite"])

                            elif family == "drafts":
                                data, _ = _assert_success(
                                    self,
                                    client.post(
                                        "/api/v1/listings/drafts",
                                        json={
                                            "title": f"Draft {mode}",
                                            "subtitle": "Matrix subtitle",
                                            "description": "Matrix description",
                                            "category_id": "cat_home",
                                            "price_minor": 19900,
                                            "original_price_minor": 29900,
                                            "currency": "CNY",
                                            "condition_level": "good",
                                            "location_city": "Matrix City",
                                            "draft_payload_json": {"mode": mode},
                                        },
                                        headers=headers,
                                    ),
                                )
                                draft_id = data["id"]
                                if mode % 4 == 0:
                                    detail, _ = _assert_success(self, client.get(f"/api/v1/listings/drafts/{draft_id}", headers=headers))
                                    self.assertEqual(detail["id"], draft_id)
                                elif mode % 4 == 1:
                                    updated, _ = _assert_success(
                                        self,
                                        client.patch(
                                            f"/api/v1/listings/drafts/{draft_id}",
                                            json={"title": f"Updated Draft {mode}", "draft_payload_json": {"updated": True}},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(updated["title"], f"Updated Draft {mode}")
                                elif mode % 4 == 2:
                                    published, _ = _assert_success(self, client.post(f"/api/v1/listings/drafts/{draft_id}/publish", headers=headers))
                                    self.assertEqual(published["status"], "live")
                                else:
                                    response = client.get("/api/v1/listings/drafts/missing", headers=headers)
                                    _assert_error(self, response, 404, 3004)

                            elif family == "conversations":
                                conversation_id = harness.make_conversation(buyer_id=current_user_id, seller_id=harness.demo_seller_id, listing_id=harness.demo_listing_id)
                                if mode % 4 == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/conversations", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif mode % 4 == 1:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/conversations/{conversation_id}", headers=headers))
                                    self.assertEqual(data["conversation"]["id"], conversation_id)
                                elif mode % 4 == 2:
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            f"/api/v1/conversations/{conversation_id}/messages",
                                            json={"content_text": f"Message {mode}", "message_type": "text"},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["conversation_id"], conversation_id)
                                else:
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            f"/api/v1/conversations/{conversation_id}/read",
                                            json={"last_read_message_id": f"message_{mode}"},
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["conversation_id"], conversation_id)

                            elif family == "orders":
                                order_id = harness.make_order(buyer_id=current_user_id, seller_id=harness.demo_seller_id, listing_id=harness.demo_listing_id, status="shipped")
                                if mode % 4 == 0:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/orders/{order_id}", headers=headers))
                                    self.assertEqual(data["order"]["id"], order_id)
                                elif mode % 4 == 1:
                                    data, _ = _assert_success(self, client.get(f"/api/v1/orders/{order_id}/timeline", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif mode % 4 == 2:
                                    data, _ = _assert_success(self, client.post(f"/api/v1/orders/{order_id}/confirm-receipt", headers=headers))
                                    self.assertEqual(data["order"]["status"], "completed")
                                else:
                                    data, _ = _assert_success(self, client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers))
                                    self.assertEqual(data["order"]["status"], "cancelled")

                            elif family == "reviews":
                                order_id = harness.make_order(buyer_id=current_user_id, seller_id=harness.demo_seller_id, listing_id=harness.demo_listing_id, status="completed")
                                if mode % 4 == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/reviews", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif mode % 4 == 1:
                                    data, _ = _assert_success(
                                        self,
                                        client.post(
                                            "/api/v1/reviews",
                                            json={
                                                "order_id": order_id,
                                                "listing_id": harness.demo_listing_id,
                                                "rating": 5,
                                                "tags": ["发货快", "与描述一致"],
                                                "content": f"Review {mode}",
                                                "media_asset_ids": [f"media_{mode}"],
                                                "anonymity_enabled": False,
                                            },
                                            headers=headers,
                                        ),
                                    )
                                    self.assertEqual(data["order_id"], order_id)
                                elif mode % 4 == 2:
                                    review_id = harness.make_review(order_id=order_id)
                                    data, _ = _assert_success(self, client.get(f"/api/v1/reviews/{review_id}", headers=headers))
                                    self.assertEqual(data["id"], review_id)
                                else:
                                    response = client.post(
                                        "/api/v1/reviews",
                                        json={
                                            "order_id": order_id,
                                            "listing_id": harness.demo_listing_id,
                                            "rating": 0,
                                            "content": "broken",
                                        },
                                        headers=headers,
                                    )
                                    _assert_error(self, response, 422, 2001)

                            elif family == "wallet":
                                if mode % 4 == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/wallet", headers=headers))
                                    self.assertIn("transactions", data)
                                elif mode % 4 == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/wallet/transactions", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif mode % 4 == 2:
                                    data, _ = _assert_success(self, client.get("/api/v1/wallet", headers=headers))
                                    self.assertIn("account", data)
                                else:
                                    data, _ = _assert_success(self, client.get("/api/v1/wallet/transactions", headers=headers))
                                    self.assertIsInstance(data, list)

                            elif family == "membership":
                                if mode % 4 == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/membership/plans", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif mode % 4 == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/membership/subscription", headers=headers))
                                    self.assertTrue(data is None or "plan" in data)
                                elif mode % 4 == 2:
                                    data, _ = _assert_success(self, client.post("/api/v1/membership/upgrade", json={"plan_key": "gold"}, headers=headers))
                                    self.assertEqual(data["status"], "active")
                                else:
                                    response = client.post("/api/v1/membership/upgrade", json={"plan_key": "missing"}, headers=headers)
                                    _assert_error(self, response, 404, 3004)

                            else:
                                if mode % 4 == 0:
                                    data, _ = _assert_success(self, client.get("/api/v1/notifications", headers=headers))
                                    self.assertIsInstance(data, list)
                                elif mode % 4 == 1:
                                    data, _ = _assert_success(self, client.get("/api/v1/badges/summary", headers=headers))
                                    self.assertIn("unread_notifications", data)
                                elif mode % 4 == 2:
                                    data, _ = _assert_success(self, client.post("/api/v1/notifications/read", json={"read_at": None}, headers=headers))
                                    self.assertIn("read_count", data)
                                else:
                                    notification_id = f"notification_{uuid.uuid4().hex[:10]}"
                                    harness.store.upsert_record(
                                        "notification",
                                        notification_id,
                                        {
                                            "id": notification_id,
                                            "user_id": current_user_id,
                                            "notification_type": "system",
                                            "title": f"Commerce Notice {mode}",
                                            "body": "Commerce matrix notification",
                                            "entity_type": "order",
                                            "entity_id": order_id,
                                            "read_at": None,
                                            "created_at": "2026-04-10T00:00:00Z",
                                        },
                                    )
                                    data, _ = _assert_success(
                                        self,
                                        client.patch(f"/api/v1/notifications/{notification_id}/read", json={}, headers=headers),
                                    )
                                    self.assertEqual(data["id"], notification_id)

            self.assertEqual(case_count, 512)

    def test_reconstruction_matrix(self) -> None:
        families = [
            "serialize",
            "create",
            "pipeline_start",
            "pipeline_cancel",
            "mask_debug",
            "mask_preview",
            "mask_confirm",
            "viewer_publish_list_delete",
        ]

        with backend_harness("reconstruction_matrix") as harness:
            case_count = 0

            for family in families:
                for state in range(8):
                    for mode in range(8):
                        case_count += 1
                        with self.subTest(family=family, state=state, mode=mode):
                            request = SimpleNamespace(base_url="http://testserver/")

                            if family == "serialize":
                                task_id = f"serialize_{state}_{mode}_{uuid.uuid4().hex[:8]}"
                                viewer_config = {
                                    "model_rotation_deg": [float(mode), 1.0, 2.0],
                                    "model_translation": [3.0, 4.0, 5.0],
                                    "model_scale": 1.0 + mode / 10,
                                    "camera_rotation_deg": [-18.0, 26.0, 0.0],
                                    "camera_distance": 1.6,
                                }
                                task = harness.make_task(
                                    task_id=task_id,
                                    status="ready" if mode % 2 == 0 else "uploaded",
                                    quality_profile="balanced",
                                    object_masking=mode % 2 == 0,
                                    model_rel_path=f"/storage/models/{task_id}/model.ply",
                                    viewer_config=viewer_config,
                                    mask_prompt_frame_name="frame_001.jpg",
                                    mask_prompt_frame_rel_path=f"/storage/processed/{task_id}/frame_001.jpg",
                                )
                                model_dir = harness.storage_root / "models" / task_id
                                model_dir.mkdir(parents=True, exist_ok=True)
                                (model_dir / "model.ply").write_bytes(b"ply")
                                response = reconstructions_module._serialize_task(request, task)
                                self.assertEqual(response.task_id, task_id)
                                self.assertIsNotNone(response.viewer_url)
                                if mode % 2 == 0:
                                    self.assertTrue(response.object_masking)

                            elif family == "create":
                                if mode == 0:
                                    with patch.object(reconstructions_module, "_validate_uploaded_video", return_value={"streams": [{"codec_type": "video"}], "format": {"duration": 1.0}}):
                                        response = harness.client.post(
                                            "/api/v1/reconstructions",
                                            data={"title": f"Task {mode}", "description": "Desc", "price": "99.00"},
                                            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
                                        )
                                    data, _ = _assert_success(self, response, expected_status=201)
                                    self.assertEqual(data["status"], "uploaded")
                                elif mode == 1:
                                    response = harness.client.post(
                                        "/api/v1/reconstructions",
                                        data={"title": f"Task {mode}", "description": "Desc", "price": "99.00"},
                                        files={"video": ("clip.mp4", b"video-bytes", "text/plain")},
                                    )
                                    _assert_error(self, response, 400, 3001)
                                elif mode == 2:
                                    response = harness.client.post(
                                        "/api/v1/reconstructions",
                                        data={"title": f"Task {mode}", "description": "Desc", "price": "99.00"},
                                        files={"video": ("", b"video-bytes", "video/mp4")},
                                    )
                                    _assert_error(self, response, 422, 2001)
                                else:
                                    with patch.object(reconstructions_module, "_validate_uploaded_video", return_value={"streams": [{"codec_type": "video"}], "format": {"duration": 1.0}}):
                                        response = harness.client.post(
                                            "/api/v1/reconstructions",
                                            data={"title": f"Task {mode}", "description": "Desc", "price": "99.00"},
                                            files={"video": (f"clip-{mode}.mp4", b"video-bytes", "video/mp4")},
                                        )
                                    data, _ = _assert_success(self, response, expected_status=201)
                                    self.assertEqual(data["title"], f"Task {mode}")

                            elif family == "pipeline_start":
                                task_id = f"start_{state}_{mode}_{uuid.uuid4().hex[:8]}"
                                task = harness.make_task(task_id=task_id, status="uploaded" if mode % 2 == 0 else "queued", quality_profile="balanced")
                                if task["status"] == "uploaded":
                                    with patch.object(reconstructions_module, "_start_pipeline_subprocess", return_value=4321):
                                        response = harness.client.post(
                                            f"/api/v1/reconstructions/{task_id}/pipeline/start",
                                            json={"quality_profile": "balanced", "train_max_steps": 7000, "object_masking": mode % 2 == 0},
                                        )
                                    data, _ = _assert_success(self, response)
                                    self.assertEqual(data["status"], "queued")
                                else:
                                    response = harness.client.post(
                                        f"/api/v1/reconstructions/{task_id}/pipeline/start",
                                        json={"quality_profile": "balanced", "train_max_steps": 7000, "object_masking": False},
                                    )
                                    _assert_error(self, response, 409, 3002)

                            elif family == "pipeline_cancel":
                                task_id = f"cancel_{state}_{mode}_{uuid.uuid4().hex[:8]}"
                                task = harness.make_task(task_id=task_id, status="queued" if mode % 2 == 0 else "ready", quality_profile="balanced")
                                if task["status"] in {"queued", "preprocessing", "masking", "training", "exporting"}:
                                    with patch.object(reconstructions_module, "_terminate_task_processes", return_value=[4321]):
                                        response = harness.client.post(f"/api/v1/reconstructions/{task_id}/pipeline/cancel")
                                    data, _ = _assert_success(self, response)
                                    self.assertEqual(data["status"], "cancelled")
                                else:
                                    response = harness.client.post(f"/api/v1/reconstructions/{task_id}/pipeline/cancel")
                                    _assert_error(self, response, 409, 3002)

                            elif family == "mask_debug":
                                task_id = f"maskdebug_{state}_{mode}_{uuid.uuid4().hex[:8]}"
                                task = harness.make_task(task_id=task_id, status="ready", quality_profile="balanced", object_masking=False)
                                harness.prepare_mask_debug_dataset(task_id)
                                with patch.object(reconstructions_module, "select_mask_prompt_frame", return_value=None):
                                    response = harness.client.post(f"/api/v1/reconstructions/{task_id}/mask-debug")
                                data, _ = _assert_success(self, response)
                                self.assertTrue(data["object_masking"])

                            elif family == "mask_preview":
                                task_id = f"maskpreview_{state}_{mode}_{uuid.uuid4().hex[:8]}"
                                task = harness.make_task(
                                    task_id=task_id,
                                    status="awaiting_mask_prompt" if mode % 2 == 0 else "awaiting_mask_confirmation",
                                    quality_profile="balanced",
                                    object_masking=True,
                                    mask_prompt_frame_name="frame_001.jpg",
                                    mask_prompt_frame_rel_path=f"/storage/processed/{task_id}/frame_001.jpg",
                                    mask_prompt_frame_width=1920,
                                    mask_prompt_frame_height=1080,
                                )
                                harness.prepare_mask_preview_artifacts(task_id, "frame_001.jpg")
                                with patch.object(reconstructions_module, "build_sam2_preview_command", return_value=["sam2-preview"]), patch.object(
                                    reconstructions_module,
                                    "run_logged_streaming_command",
                                    return_value=SimpleNamespace(returncode=0, stderr="", stdout=""),
                                ):
                                    response = harness.client.post(
                                        f"/api/v1/reconstructions/{task_id}/mask-preview",
                                        json={
                                            "points": [
                                                {"x": 0.2, "y": 0.3, "label": 1},
                                                {"x": 0.7, "y": 0.8, "label": 0},
                                            ]
                                        },
                                    )
                                data, _ = _assert_success(self, response)
                                self.assertEqual(data["status"], "awaiting_mask_confirmation")

                            elif family == "mask_confirm":
                                task_id = f"maskconfirm_{state}_{mode}_{uuid.uuid4().hex[:8]}"
                                task = harness.make_task(
                                    task_id=task_id,
                                    status="awaiting_mask_confirmation",
                                    quality_profile="balanced",
                                    object_masking=True,
                                    mask_prompt_frame_name="frame_001.jpg",
                                    mask_prompt_frame_rel_path=f"/storage/processed/{task_id}/frame_001.jpg",
                                )
                                harness.prepare_mask_preview_artifacts(task_id, "frame_001.jpg")
                                with patch.object(reconstructions_module, "_start_pipeline_subprocess", return_value=9876):
                                    response = harness.client.post(f"/api/v1/reconstructions/{task_id}/mask-confirm")
                                data, _ = _assert_success(self, response)
                                self.assertEqual(data["status"], "queued")

                            else:
                                task_id = f"viewer_{state}_{mode}_{uuid.uuid4().hex[:8]}"
                                viewer_config = {
                                    "model_rotation_deg": [0.0, 1.0, 2.0],
                                    "model_translation": [3.0, 4.0, 5.0],
                                    "model_scale": 1.0,
                                    "camera_rotation_deg": [-18.0, 26.0, 0.0],
                                    "camera_distance": 1.6,
                                }
                                task = harness.make_task(
                                    task_id=task_id,
                                    status="ready" if mode % 2 == 0 else "uploaded",
                                    quality_profile="balanced",
                                    object_masking=False,
                                    model_rel_path=f"/storage/models/{task_id}/model.ply",
                                    viewer_config=viewer_config,
                                )
                                model_dir = harness.storage_root / "models" / task_id
                                model_dir.mkdir(parents=True, exist_ok=True)
                                (model_dir / "model.ply").write_bytes(b"ply")
                                if mode % 4 == 0:
                                    response = harness.client.put(
                                        f"/api/v1/reconstructions/{task_id}/viewer",
                                        json={
                                            "model_rotation_deg": [0, 10, 20],
                                            "model_translation": [1, 2, 3],
                                            "model_scale": 1.25,
                                            "camera_rotation_deg": [-15, 30, 0],
                                            "camera_distance": 1.75,
                                        },
                                    )
                                    data, _ = _assert_success(self, response)
                                    self.assertEqual(data["task_id"], task_id)
                                elif mode % 4 == 1:
                                    response = harness.client.post(f"/api/v1/reconstructions/{task_id}/publish")
                                    if task["status"] == "ready":
                                        data, _ = _assert_success(self, response)
                                        self.assertTrue(data["is_published"])
                                    else:
                                        _assert_error(self, response, 409, 3002)
                                elif mode % 4 == 2:
                                    response = harness.client.get("/api/v1/reconstructions", params={"status": "ready,uploaded"})
                                    self.assertEqual(response.status_code, 200)
                                    data = response.json()
                                    self.assertIsInstance(data, list)
                                else:
                                    response = harness.client.delete(f"/api/v1/reconstructions/{task_id}")
                                    self.assertEqual(response.status_code, 204)

            self.assertEqual(case_count, 512)


if __name__ == "__main__":
    import unittest

    unittest.main()
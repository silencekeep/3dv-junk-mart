from __future__ import annotations

import os
import unittest

from backend.app.services.trainer_service_client import TrainerServiceClient


RUN_REMOTE_TESTS = os.getenv("RUN_REMOTE_3DGS_CONNECTIVITY_TESTS") == "1"
REMOTE_BASE_URL = (os.getenv("REMOTE_3DGS_BASE_URL") or "http://222.199.216.192:9000").rstrip("/")
REMOTE_PUBLIC_BASE_URL = (os.getenv("REMOTE_3DGS_PUBLIC_BASE_URL") or REMOTE_BASE_URL).rstrip("/")


@unittest.skipUnless(RUN_REMOTE_TESTS, "Remote 3DGS connectivity tests are opt-in.")
class Remote3DgsConnectivityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TrainerServiceClient(
            base_url=REMOTE_BASE_URL,
            public_base_url=REMOTE_PUBLIC_BASE_URL,
        )

    def tearDown(self) -> None:
        self.client.close()

    def test_health_and_task_listing(self) -> None:
        health = self.client.health()
        self.assertIsInstance(health, dict)
        self.assertTrue(health.get("repo_root"))
        self.assertTrue(health.get("viewer_root"))
        self.assertEqual(health.get("public_base_url"), REMOTE_PUBLIC_BASE_URL)

        tasks = self.client.list_tasks()
        self.assertIsInstance(tasks, list)
        self.assertGreater(len(tasks), 0)
        sample_task = tasks[0]
        self.assertIn("task_id", sample_task)
        self.assertTrue(sample_task.get("video_url") or sample_task.get("model_url"))

    def test_viewer_config_round_trip(self) -> None:
        tasks = self.client.list_tasks()
        task = next((item for item in tasks if item.get("model_url")), None)
        if task is None:
            self.skipTest("Remote service did not return a task with a generated model.")

        task_id = str(task["task_id"])
        viewer_config = task.get("viewer_config") or {}
        payload = {
            "model_rotation_deg": viewer_config.get("model_rotation_deg") or [0.0, 0.0, 0.0],
            "model_translation": viewer_config.get("model_translation") or [0.0, 0.0, 0.0],
            "model_scale": viewer_config.get("model_scale") or 1.0,
            "camera_rotation_deg": viewer_config.get("camera_rotation_deg") or [-18.0, 26.0, 0.0],
            "camera_distance": viewer_config.get("camera_distance") or 1.6,
        }

        response = self.client.update_viewer_config(task_id, payload)
        self.assertEqual(response["task_id"], task_id)
        self.assertEqual(response["viewer_config"], payload)

        detail = self.client.get_task(task_id)
        self.assertEqual(detail.get("viewer_config"), payload)


if __name__ == "__main__":
    unittest.main()
from __future__ import annotations

import importlib.util
from contextlib import closing
import sqlite3
import tarfile
import tempfile
import threading
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class _DeploymentHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.endswith("/health"):
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path.endswith(".ply") or self.path.endswith("index.html"):
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def _load_module(relative_path: str, module_name: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class DeploymentArtifactsTestCase(unittest.TestCase):
    def test_artifact_files_include_expected_runtime_settings(self) -> None:
        backend_service = (REPO_ROOT / "deploy/linux/systemd/3dgs-backend.service").read_text(encoding="utf-8")
        trainer_service = (REPO_ROOT / "deploy/linux/systemd/3dgs-trainer.service").read_text(encoding="utf-8")
        backup_service = (REPO_ROOT / "deploy/linux/systemd/3dgs-backup.service").read_text(encoding="utf-8")
        backup_timer = (REPO_ROOT / "deploy/linux/systemd/3dgs-backup.timer").read_text(encoding="utf-8")
        health_service = (REPO_ROOT / "deploy/linux/systemd/3dgs-healthcheck.service").read_text(encoding="utf-8")
        health_timer = (REPO_ROOT / "deploy/linux/systemd/3dgs-healthcheck.timer").read_text(encoding="utf-8")
        nginx_conf = (REPO_ROOT / "deploy/linux/nginx/3dgs-marketplace.conf").read_text(encoding="utf-8")
        logrotate_conf = (REPO_ROOT / "deploy/linux/logrotate/3dgs-marketplace").read_text(encoding="utf-8")
        deploy_readme = (REPO_ROOT / "deploy/README.md").read_text(encoding="utf-8")

        self.assertIn("Restart=always", backend_service)
        self.assertIn("EnvironmentFile=/etc/3dgs-marketplace/backend.env", backend_service)
        self.assertIn("LogsDirectory=3dgs-marketplace", backend_service)
        self.assertIn("ReadWritePaths=/data/3dgs-marketplace/backend /var/log/3dgs-marketplace", backend_service)
        self.assertIn("ExecStart=/opt/3dgs-marketplace/repo/backend/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000", backend_service)

        self.assertIn("Restart=always", trainer_service)
        self.assertIn("EnvironmentFile=/etc/3dgs-marketplace/trainer.env", trainer_service)
        self.assertIn("ExecStart=/opt/conda/envs/3dgs_app/bin/python -m uvicorn trainer_service.app:app --host 127.0.0.1 --port 9000", trainer_service)

        self.assertIn("ExecStart=/opt/3dgs-marketplace/repo/backend/.venv/bin/python /opt/3dgs-marketplace/repo/deploy/scripts/backup_runtime_state.py", backup_service)
        self.assertIn("OnCalendar=daily", backup_timer)
        self.assertIn("Persistent=true", backup_timer)

        self.assertIn("ExecStart=/opt/3dgs-marketplace/repo/backend/.venv/bin/python /opt/3dgs-marketplace/repo/deploy/scripts/check_runtime_health.py", health_service)
        self.assertIn("OnBootSec=5min", health_timer)
        self.assertIn("OnUnitActiveSec=5min", health_timer)

        self.assertIn("proxy_pass http://127.0.0.1:8000;", nginx_conf)
        self.assertIn("proxy_pass http://127.0.0.1:9000;", nginx_conf)
        self.assertIn("client_max_body_size 512m;", nginx_conf)
        self.assertIn("client_max_body_size 1g;", nginx_conf)

        self.assertIn("/var/log/3dgs-marketplace/backend.log", logrotate_conf)
        self.assertIn("/var/log/3dgs-marketplace/trainer.log", logrotate_conf)
        self.assertIn("copytruncate", logrotate_conf)

        self.assertIn("backup_runtime_state.py", deploy_readme)
        self.assertIn("check_runtime_health.py", deploy_readme)
        self.assertIn("systemd", deploy_readme)
        self.assertIn("logrotate", deploy_readme)

    def test_backup_script_creates_database_and_archive_backups(self) -> None:
        backup_module = _load_module("deploy/scripts/backup_runtime_state.py", "backup_runtime_state")

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            database_path = temp_dir / "business.db"
            backup_root = temp_dir / "backups"
            model_root = temp_dir / "models"
            log_root = temp_dir / "logs"

            connection = sqlite3.connect(database_path)
            try:
                connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
                connection.execute("INSERT INTO items (name) VALUES ('camera tripod')")
                connection.commit()
            finally:
                connection.close()

            (model_root / "latest").mkdir(parents=True)
            (model_root / "latest" / "model.ply").write_text("ply\n", encoding="utf-8")
            log_root.mkdir(parents=True)
            (log_root / "backend.log").write_text("backend started\n", encoding="utf-8")

            artifacts = backup_module.backup_runtime_state(
                database_path,
                backup_root,
                model_root=model_root,
                log_root=log_root,
            )

            sqlite_backups = sorted((backup_root / "sqlite").glob("*.db"))
            model_archives = sorted((backup_root / "models").glob("*.tar.gz"))
            log_archives = sorted((backup_root / "logs").glob("*.tar.gz"))

            self.assertEqual(len(sqlite_backups), 1)
            self.assertEqual(len(model_archives), 1)
            self.assertEqual(len(log_archives), 1)
            self.assertEqual(len(artifacts), 3)

            with closing(sqlite3.connect(sqlite_backups[0])) as connection:
                row = connection.execute("SELECT name FROM items").fetchone()
            self.assertEqual(row[0], "camera tripod")

            with tarfile.open(model_archives[0], "r:gz") as archive:
                members = archive.getnames()
            self.assertTrue(any(name.endswith("latest/model.ply") for name in members))

            with tarfile.open(log_archives[0], "r:gz") as archive:
                members = archive.getnames()
            self.assertTrue(any(name.endswith("backend.log") for name in members))

    def test_healthcheck_script_validates_health_and_static_resources(self) -> None:
        health_module = _load_module("deploy/scripts/check_runtime_health.py", "check_runtime_health")

        server = ThreadingHTTPServer(("127.0.0.1", 0), _DeploymentHealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def _cleanup_server() -> None:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.addCleanup(_cleanup_server)

        base_url = f"http://127.0.0.1:{server.server_port}"
        results = health_module.check_deployment_health(
            backend_health_url=f"{base_url}/backend/health",
            trainer_health_url=f"{base_url}/trainer/health",
            model_url=f"{base_url}/storage/models/latest/model.ply",
            viewer_url=f"{base_url}/viewer/index.html",
            timeout_seconds=2,
        )

        self.assertEqual(len(results), 4)
        self.assertTrue(all(result.url.startswith(base_url) for result in results))
        self.assertTrue(all(result.payload is not None or result.status_code == 200 for result in results))


if __name__ == "__main__":
    unittest.main()
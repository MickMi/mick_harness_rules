"""Focused environment isolation checks; all writable fixtures are temporary."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tests.test_harness_observe import OBSERVE, ROOT, SCRIPT, plan_text


class ObserverEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "AGENTS.md").write_text("# Harness\n")
        (self.project / "plan.md").write_text(plan_text())
        self.state = self.root / "state"
        self.state.mkdir()
        (self.state / "registered-projects").write_text(f"{self.project}\n")
        self.env = mock.patch.dict(os.environ, {
            "HOME": str(self.root),
            "MICK_HARNESS_STATE_DIR": str(self.state),
            "MICK_HARNESS_STATE_ROOT": str(self.state),
            "MICK_BRAIN_ROOT": str(self.root / "brain"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def server(self, *, portfolio=True):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen([
            sys.executable, "-B", str(SCRIPT), "watch",
            *( ["--all"] if portfolio else [str(self.project)] ),
            "--environment", "development", "--port", str(port), "--scan-interval", "0.05",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        def stop():
            process.terminate()
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=3)

        self.addCleanup(stop)
        base = f"http://127.0.0.1:{port}"
        for _ in range(100):
            if process.poll() is not None:
                self.fail(f"preview failed: {process.communicate()}")
            try:
                with urlopen(base + "/healthz", timeout=0.2) as response:
                    if response.status == 200:
                        return base
            except (URLError, TimeoutError):
                time.sleep(0.05)
        self.fail("preview did not start")

    def get(self, base, path):
        with urlopen(base + path, timeout=5) as response:
            return json.loads(response.read())

    def test_development_launch_agent_is_separate_and_stable(self):
        prod = OBSERVE.build_launch_agent_plist(ROOT, self.state)
        dev = OBSERVE.build_launch_agent_plist(ROOT, self.state, port=6426, environment="development")
        self.assertEqual(prod["Label"], "com.mick.harness.observer")
        self.assertEqual(dev["Label"], "com.mick.harness.observer.dev")
        self.assertIn("development", dev["ProgramArguments"])
        self.assertIn("6426", dev["ProgramArguments"])
        self.assertNotEqual(dev["StandardOutPath"], prod["StandardOutPath"])
        self.assertTrue(dev["KeepAlive"])
        self.assertTrue(dev["RunAtLoad"])
        self.assertNotEqual(OBSERVE.launch_agent_path(self.root),
                            OBSERVE.launch_agent_path(self.root, environment="development"))
        self.assertEqual(OBSERVE.environment_port("development"), 6426)
        with mock.patch.object(OBSERVE.sys, "platform", "darwin"):
            with self.assertRaisesRegex(OBSERVE.ObserveError, "stable port"):
                OBSERVE.install_service(port=6433, home=self.root, environment="development")
        self.assertFalse((self.root / "Library").exists())

    def test_install_development_does_not_modify_or_restart_production(self):
        production = OBSERVE.launch_agent_path(self.root)
        production.parent.mkdir(parents=True)
        production.write_bytes(b"existing-production-config")
        health = {"service_name": OBSERVE.SERVICE_NAME,
                  "service_label": "com.mick.harness.observer.dev", "port": 6426}
        with (mock.patch.object(OBSERVE.sys, "platform", "darwin"),
              mock.patch.object(OBSERVE, "launch_agent_loaded", return_value=False),
              mock.patch.object(OBSERVE, "observer_health", return_value=health),
              mock.patch.object(OBSERVE, "wait_for_observer", return_value=health),
              mock.patch.object(OBSERVE, "run_launchctl") as launchctl):
            result = OBSERVE.install_service(home=self.root, environment="development")
        self.assertTrue(result["healthy"])
        self.assertEqual(production.read_bytes(), b"existing-production-config")
        for call in launchctl.call_args_list:
            for argument in call.args[0]:
                if "com.mick.harness.observer" in argument:
                    self.assertIn("com.mick.harness.observer.dev", argument)

    def test_wrong_service_on_development_port_is_not_healthy(self):
        with (mock.patch.object(OBSERVE, "launch_agent_loaded", return_value=True),
              mock.patch.object(OBSERVE, "observer_health", return_value={
                  "service_name": OBSERVE.SERVICE_NAME, "service_label": OBSERVE.SERVICE_LABEL})):
            self.assertFalse(OBSERVE.service_status(home=self.root, environment="development")["healthy"])

    def test_missing_snapshot_is_projected_without_persisting(self):
        OBSERVE.init_runtime(self.project)
        _, run = OBSERVE.current_run(self.project)
        (run / "snapshot.json").unlink()
        before = self.files()
        self.assertTrue(OBSERVE.status_runtime(self.project)["snapshot"]["run"])
        self.assertEqual(before, self.files())

    def test_slow_git_read_returns_unavailable_without_breaking_request(self):
        with mock.patch.object(OBSERVE.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 2)):
            result = OBSERVE.run_git(self.project, ["tag", "--list"])
            self.assertEqual(result.returncode, 124)
            self.assertEqual(result.stdout, "")
            self.assertEqual(OBSERVE._git_worktree_records(self.project), [])

    def test_empty_project_preview_never_initializes_records(self):
        before = self.files()
        base = self.server(portfolio=False)
        self.assertEqual(self.get(base, "/api/index.json")["runs"], [])
        self.get(base, "/api/portfolio.json?detail=full")
        identifier = OBSERVE.project_id(self.project)
        with self.assertRaises(HTTPError) as failure:
            self.get(base, f"/api/projects/{identifier}/workspace.json?scope=overview")
        self.assertEqual(failure.exception.code, 404)
        self.assertEqual(before, self.files())

    def test_development_http_reads_live_records_but_cannot_write(self):
        OBSERVE.init_runtime(self.project)
        installed = self.root / ".mick-harness"
        installed.mkdir()
        (installed / "VERSION").write_text("0.24.0\n")
        before = self.files()
        base = self.server()
        health = self.get(base, "/healthz")
        self.assertFalse(health["ingest_enabled"])
        self.assertFalse(health["collector_enabled"])
        self.assertIsNone(health["last_scan_at"])
        runtime = self.get(base, "/api/runtime.json")
        self.assertEqual(runtime["environment"], "development")
        self.assertTrue(runtime["read_only"])
        self.assertEqual(runtime["version"], (ROOT / "VERSION").read_text().strip())
        self.assertEqual(runtime["source_path"], str(ROOT))
        self.assertEqual(self.get(base, "/api/harness/versions.json")["baseline"]["version"], "0.24.0")
        with urlopen(base + "/", timeout=2) as response:
            html = response.read().decode()
        self.assertNotIn("/* HARNESS_RUNTIME_BOOTSTRAP */ null", html)
        self.assertIn(runtime["started_at"], html)
        identifier = OBSERVE.project_id(self.project)
        for path in ["/api/portfolio.json", "/api/portfolio.json?detail=full",
                     f"/api/projects/{identifier}/index.json",
                     f"/api/projects/{identifier}/workspace.json?scope=overview",
                     f"/api/projects/{identifier}/workspace.json",
                     "/api/operations.json", "/api/reporting.json",
                     "/api/brain/candidates.json", "/api/brain/project-memory/summary.json",
                     "/api/harness/improvements.json"]:
            self.get(base, path)
        for path in ["/api/v1/events", "/api/operations/preview", "/api/brain/sync",
                     "/api/reporting/configuration", f"/api/projects/{identifier}/unregister"]:
            with self.assertRaises(HTTPError) as failure:
                urlopen(Request(base + path, data=b"{}", method="POST",
                                headers={"Content-Type": "application/json"}), timeout=2)
            self.assertEqual(failure.exception.code, 403)
            self.assertEqual(json.loads(failure.exception.read())["code"], "development-read-only")
        self.assertEqual(before, self.files())
        # Data is read live from the one existing ledger, not a preview copy.
        OBSERVE.ingest_envelope(self.project, OBSERVE.build_work_envelope(
            self.project, event_type="work.round_started", role="Executor", round_ref="later",
            objective="Written by the real collector", status="active", idempotency_key="later",
        ))
        changed = self.files()
        fresh = self.get(base, "/api/portfolio.json")
        self.assertEqual(fresh["projects"][0]["recent_work"]["objective"], "Written by the real collector")
        self.assertEqual(changed, self.files())


if __name__ == "__main__":
    unittest.main()

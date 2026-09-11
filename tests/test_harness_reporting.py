"""Isolated contracts for session reporting; never uses personal project/Brain data."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
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

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REPORTING = load("harness-reporting")
OBSERVE = load("harness-observe")


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / "demo"
        self.project.mkdir()
        (self.project / "AGENTS.md").write_text("# Harness\n")
        self.state = self.base / "state"
        self.state.mkdir()
        self.env = mock.patch.dict(os.environ, {
            "MICK_HARNESS_STATE_DIR": str(self.state),
            "MICK_HARNESS_STATE_ROOT": str(self.state),
            "MICK_BRAIN_ROOT": str(self.base / "brain"),
            "MICK_BRAIN_MODE": "disabled",
            "MICK_HARNESS_OBSERVER_PORT": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.project_id = OBSERVE.project_id(self.project)
        OBSERVE.default_registry_path().write_text(str(self.project) + "\n")

    def change(self, action="global", **values):
        return REPORTING.change_configuration({"action": action, "revision": REPORTING.configuration()["revision"], **values}, {self.project_id})

    def record(self, **values):
        REPORTING.record(**{"platform": "codex", "event": "Stop", "cwd": self.project, "project_id": self.project_id,
                            "started_at": REPORTING.now_iso(), "duration_ms": 8, "status": "skipped", "reason": "missing_turn", **values})

    def hook(self, event="UserPromptSubmit", *, platform="codex", cwd=None, raw=None, **values):
        payload = {"hook_event_name": event, "cwd": str(cwd or self.project), "session_id": "private-session", **values}
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/harness-observe-hook.py"), "--platform", platform],
                                input=raw if raw is not None else json.dumps(payload), text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def events(self):
        _, directory = OBSERVE.current_run(self.project)
        return OBSERVE.load_events(directory / "events.jsonl")

    def test_default_does_not_create_settings_and_matches_observer_state_root(self):
        self.assertTrue(REPORTING.policy()["enabled"])
        self.assertFalse(REPORTING.root().exists())
        self.assertEqual(REPORTING.root().parent, OBSERVE.default_state_root())
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.base / "xdg")}, clear=True):
            self.assertEqual(REPORTING.root().parent, OBSERVE.default_state_root())

    def test_master_pause_project_override_inherit_and_persistence(self):
        self.change("project", project_id=self.project_id, enabled=False)
        self.assertFalse(REPORTING.policy(self.project_id)["enabled"])
        self.assertTrue(REPORTING.policy("different")["enabled"])
        self.change("project", project_id=self.project_id, enabled=True)
        self.change(enabled=False)
        self.assertEqual(REPORTING.policy(self.project_id), {"enabled": False, "source": "global", "reason": "reporting_paused"})
        self.change(enabled=True)
        self.change("project", project_id=self.project_id, enabled=None)
        self.assertEqual(REPORTING.policy(self.project_id)["source"], "global")
        self.assertTrue(load("harness-reporting").policy(self.project_id)["enabled"])
        self.assertEqual((REPORTING.root() / "configuration.json").stat().st_mode & 0o777, 0o600)

    def test_settings_cas_rejects_stale_unknown_actions_and_unregistered_projects(self):
        self.change(enabled=False)
        invalid = [{"action": "global", "revision": 0, "enabled": True},
                   {"action": [], "revision": 1, "enabled": True},
                   {"action": "global", "revision": 1, "enabled": "true"},
                   {"action": "global", "revision": 1, "enabled": True, "prompt": "no"},
                   {"action": "project", "revision": 1, "project_id": "unknown", "enabled": True}]
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(REPORTING.ReportingError):
                REPORTING.change_configuration(body, {self.project_id})
        self.assertFalse(REPORTING.policy()["enabled"])

    def test_corrupt_settings_fail_closed_without_overwriting(self):
        REPORTING.atomic_json("configuration.json", {"enabled": "true"})
        before = (REPORTING.root() / "configuration.json").read_bytes()
        self.assertEqual(REPORTING.policy()["reason"], "invalid_configuration")
        with self.assertRaises(REPORTING.ReportingError):
            self.change(enabled=True)
        self.hook(turn_id="turn")
        self.assertEqual(REPORTING.records()[-1]["reason"], "invalid_configuration")
        self.assertEqual((REPORTING.root() / "configuration.json").read_bytes(), before)

    def test_pause_blocks_client_server_and_preserves_existing_queue(self):
        envelope = OBSERVE.build_agent_envelope(self.project, platform="codex", state="turn_started", session_ref="s", turn_ref="t")
        queued = OBSERVE.queue_envelope(self.project, envelope)
        self.change(enabled=False)
        self.assertTrue(OBSERVE.ingest_envelope(self.project, envelope)["skipped"])
        with mock.patch.object(OBSERVE, "urlopen", side_effect=AssertionError("must not send")):
            self.assertTrue(OBSERVE.submit_envelope(self.project, envelope)["skipped"])
        self.assertEqual(OBSERVE.replay_outbox(self.project)["remaining"], 1)
        self.assertTrue(queued.exists())
        self.hook(turn_id="new-turn")
        self.assertEqual(len(list(OBSERVE.outbox_root(self.project).glob("*.json"))), 1)
        self.assertEqual(REPORTING.records()[-1]["reason"], "reporting_paused")
        self.change(enabled=True)
        self.assertEqual(OBSERVE.replay_outbox(self.project)["replayed"], 1)
        self.assertFalse(queued.exists())
        self.assertTrue(any(e["type"] == "agent.turn_observed" for e in self.events()))

    def test_project_file_collector_still_runs_while_session_reporting_is_paused(self):
        (self.project / "plan.md").write_text("# Plan\n\n## Steps\n\n- [ ] 1. Sample task\n")
        self.change(enabled=False)
        self.assertGreater(OBSERVE.sync_runtime(self.project)["appended"], 0)
        self.assertTrue(any(e["type"] == "task.discovered" for e in self.events()))

    def test_unresolved_workspace_can_be_bound_explicitly_for_future_events(self):
        mirror = self.base / "mirror"
        mirror.mkdir()
        self.hook(cwd=mirror, turn_id="first")
        self.assertEqual(REPORTING.records()[-1]["reason"], "project_unresolved")
        ref = REPORTING.workspace_ref(mirror)
        self.change("associate", workspace_ref=ref, project_id=self.project_id)
        self.assertEqual(OBSERVE.resolve_agent_project(mirror), self.project)
        self.hook(cwd=mirror, turn_id="second")
        records = REPORTING.records()
        self.assertEqual(records[0]["reason"], "project_unresolved")
        self.assertEqual(records[-1]["status"], "written_local")
        self.assertEqual(records[-1]["project_id"], self.project_id)
        self.change("associate", workspace_ref=ref, project_id=None)
        self.assertIsNone(OBSERVE.resolve_agent_project(mirror))

    def test_unobserved_workspace_cannot_be_bound(self):
        with self.assertRaises(REPORTING.ReportingError):
            self.change("associate", workspace_ref="a" * 32, project_id=self.project_id)

    def test_claude_missing_turn_id_full_lifecycle_two_turns_and_duplicate_stop(self):
        self.hook("SessionStart", platform="claude")
        for _ in range(2):
            self.hook(platform="claude", prompt="never persist this")
            stop = self.hook("Stop", platform="claude")
            self.assertEqual(json.loads(stop.stdout), {"continue": True})
            self.hook("Stop", platform="claude")
        self.hook("SessionEnd", platform="claude")
        turns = [e for e in self.events() if e["type"] == "agent.turn_observed"]
        self.assertEqual(len(turns), 4)
        self.assertEqual(len({e["subject"]["id"] for e in turns}), 2)
        self.assertEqual(REPORTING.read_json("turns.json", {}), {})
        self.assertTrue(all(item["status"] == "written_local" for item in REPORTING.records()))

    def test_missing_turn_malformed_inputs_and_size_have_truthful_diagnostics(self):
        for raw, reason in [(None, "missing_turn"), ("{", "invalid_payload"), ("[]", "invalid_payload"),
                            (json.dumps({"hook_event_name": []}), "unsupported_event"), ("x" * 1_048_577, "payload_too_large")]:
            with self.subTest(reason=reason):
                self.hook(raw=raw)
                self.assertEqual(REPORTING.records()[-1]["reason"], reason)
        self.hook("Stop", platform="claude")
        self.assertEqual(REPORTING.records()[-1]["reason"], "missing_turn")

    def test_diagnostics_never_keep_chat_content_or_raw_identifiers(self):
        secrets = {"prompt": "private prompt sentinel", "last_assistant_message": "private answer sentinel", "transcript_path": "/private/transcript-sentinel"}
        self.hook(turn_id="private-turn-sentinel", **secrets)
        stored = (REPORTING.root() / "records.json").read_text()
        for secret in [*secrets.values(), "private-session", "private-turn-sentinel"]:
            self.assertNotIn(secret, stored)
        self.assertEqual(REPORTING.records()[-1]["status"], "written_local")
        # Build a synthetic value at runtime; keep credential-shaped literals out of the repository.
        fake_token = "github" + "_pat_" + "1234567890" * 2
        self.assertNotIn(fake_token, REPORTING.safe_path(Path("/tmp") / fake_token / "project"))

    def test_failed_submission_is_visible_without_raw_error_details(self):
        with mock.patch.dict(os.environ, {"MICK_HARNESS_OBSERVER_PORT": "private-invalid-port-sentinel"}):
            result = self.hook(turn_id="failed")
        self.assertEqual(REPORTING.records()[-1]["status"], "failed")
        self.assertEqual(REPORTING.records()[-1]["reason"], "submission_failed")
        self.assertNotIn("private-invalid-port-sentinel", result.stderr + json.dumps(REPORTING.records()))

    def test_concurrent_configuration_updates_require_a_fresh_revision(self):
        def change(_):
            try:
                REPORTING.change_configuration({"action": "global", "revision": 0, "enabled": False}, {self.project_id})
                return "saved"
            except REPORTING.ReportingError:
                return "conflict"
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(change, range(8)))
        self.assertEqual(results.count("saved"), 1)
        self.assertEqual(REPORTING.configuration()["revision"], 1)

    def test_records_are_bounded_and_concurrent_writers_do_not_lose_updates(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.record(), range(32)))
        self.assertEqual(len(REPORTING.records()), 32)
        entries = REPORTING.records()
        REPORTING.atomic_json("records.json", [entries[0]] * 500)
        self.record(reason="reporting_paused")
        self.assertEqual(len(REPORTING.records()), 500)
        self.assertEqual(REPORTING.records()[-1]["reason"], "reporting_paused")

    def test_snapshot_empty_or_broken_history_never_claims_health_or_trust(self):
        value = REPORTING.snapshot([])
        self.assertIsNone(value["last_trigger_at"])
        self.assertEqual(value["host_trust"], "not_verified")
        REPORTING.atomic_json("records.json", [None])
        self.assertEqual(REPORTING.snapshot([])["history_error"], "trigger_records_unreadable")

    def start_server(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        process = subprocess.Popen([sys.executable, "-B", str(ROOT / "scripts/harness-observe.py"), "watch", "--all", "--port", str(self.port), "--scan-interval", "0.2"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        def stop():
            process.terminate()
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=3)
        self.addCleanup(stop)
        for _ in range(60):
            try:
                with urlopen(self.url + "/healthz", timeout=0.2):
                    return
            except (URLError, TimeoutError):
                time.sleep(0.05)
        self.fail("Isolated test server did not start")

    def request(self, body=None, headers=None, path="/api/reporting.json"):
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.url + path, data=data, headers=headers or {})
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_http_auth_origin_validation_cas_and_persistent_settings(self):
        self.start_server()
        status, value = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(value["projects"][0]["project_id"], self.project_id)
        self.assertEqual(self.request(headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request(headers={"Host": "evil.example"})[0], 403)
        headers = {"Content-Type": "application/json", "X-Harness-Action-Token": value["action_token"]}
        body = {"action": "global", "revision": 0, "enabled": False}
        path = "/api/reporting/configuration"
        self.assertEqual(self.request(body, path=path)[0], 401)
        self.assertEqual(self.request(body, {**headers, "Origin": "https://evil.example"}, path)[0], 403)
        self.assertEqual(self.request(body, {**headers, "Content-Type": "text/plain"}, path)[0], 415)
        self.assertEqual(self.request({**body, "pad": "x" * 8200}, headers, path)[0], 413)
        self.assertEqual(self.request({**body, "action": []}, headers, path)[0], 409)
        self.assertEqual(self.request(body, headers, path)[0], 200)
        self.assertEqual(self.request(body, headers, path)[0], 409)
        self.assertFalse(self.request()[1]["configuration"]["enabled"])
        self.assertFalse(REPORTING.policy()["enabled"])

    def test_live_hook_delivery_then_pause_has_no_false_success(self):
        self.start_server()
        with mock.patch.dict(os.environ, {"MICK_HARNESS_OBSERVER_PORT": str(self.port)}):
            self.hook(turn_id="accepted")
            self.assertEqual(self.request()[1]["records"][0]["status"], "delivered")
            self.change(enabled=False)
            self.hook(turn_id="paused")
        value = self.request()[1]
        self.assertEqual(value["records"][0]["status"], "skipped")
        self.assertEqual(value["records"][0]["reason"], "reporting_paused")
        turns = [e for e in self.events() if e["type"] == "agent.turn_observed"]
        self.assertEqual(len(turns), 1)


if __name__ == "__main__":
    unittest.main()

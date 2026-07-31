import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capabilities.manifest import CapabilityManifest
from perception.file import FileAdapter
from provenance.store import EvidenceStore


NOW = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)


class PerceptionPipelineTests(unittest.TestCase):
    def test_file_adapter_declares_machine_readable_capability(self):
        adapter = FileAdapter(clock=lambda: NOW)
        self.assertEqual(
            adapter.manifest,
            CapabilityManifest(
                id="observe.file", version="1", access="read_only",
                input_kind="file_path", output_kind="captured_observation",
            ),
        )

    def test_first_capture_is_persisted_with_verifiable_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "outside.txt"
            source.write_text("version one", encoding="utf-8")
            store = EvidenceStore(root / "state")

            result = store.ingest(FileAdapter(clock=lambda: NOW).observe(source))

            self.assertTrue(result.is_new)
            self.assertEqual(result.observation.observed_at, NOW)
            self.assertTrue(store.verify(result.evidence.id))
            self.assertEqual(store.snapshot(result.evidence.id), b"version one")

    def test_same_content_is_idempotent_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "outside.txt"
            source.write_bytes(b"same")
            capture = FileAdapter(clock=lambda: NOW).observe(source)

            first = EvidenceStore(root / "state").ingest(capture)
            second = EvidenceStore(root / "state").ingest(capture)

            self.assertTrue(first.is_new)
            self.assertFalse(second.is_new)
            self.assertEqual(first.observation.id, second.observation.id)
            self.assertEqual(EvidenceStore(root / "state").count(), 1)

    def test_changed_content_creates_new_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "outside.txt"
            adapter = FileAdapter(clock=lambda: NOW)
            store = EvidenceStore(root / "state")
            source.write_bytes(b"one")
            first = store.ingest(adapter.observe(source))
            source.write_bytes(b"two")
            second = store.ingest(adapter.observe(source))

            self.assertNotEqual(first.observation.id, second.observation.id)
            self.assertEqual(store.count(), 2)
            self.assertEqual(store.history(source.resolve().as_uri()), [
                first.observation.id, second.observation.id,
            ])

    def test_missing_file_is_not_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                FileAdapter(clock=lambda: NOW).observe(Path(directory) / "missing")


if __name__ == "__main__":
    unittest.main()

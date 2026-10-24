import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_run_artifacts.py"
SPEC = importlib.util.spec_from_file_location("verify_run_artifacts", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def write_manifest(tmp_path: Path, name: str, content: bytes) -> Path:
    (tmp_path / name).write_bytes(content)
    manifest = {
        "artifact_checksums": {
            name: {
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        }
    }
    path = tmp_path / "quickstart_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_artifact_verifier_accepts_intact_outputs(tmp_path):
    manifest = write_manifest(tmp_path, "results.csv", b"site,score\nA,1\n")
    verified, failures = verifier.verify_manifest(manifest)
    assert verified == ["results.csv"]
    assert failures == []


def test_artifact_verifier_detects_tampering(tmp_path):
    manifest = write_manifest(tmp_path, "results.csv", b"original")
    (tmp_path / "results.csv").write_bytes(b"modified")
    verified, failures = verifier.verify_manifest(manifest)
    assert verified == []
    assert any("mismatch" in failure for failure in failures)


def test_artifact_verifier_rejects_path_traversal(tmp_path):
    manifest = tmp_path / "quickstart_manifest.json"
    manifest.write_text(json.dumps({
        "artifact_checksums": {
            "../outside.txt": {"size_bytes": 0, "sha256": "0" * 64}
        }
    }), encoding="utf-8")
    verified, failures = verifier.verify_manifest(manifest)
    assert verified == []
    assert failures == ["unsafe artifact name: '../outside.txt'"]


def test_artifact_verifier_reports_missing_artifact(tmp_path):
    manifest = tmp_path / "quickstart_manifest.json"
    manifest.write_text(json.dumps({
        "artifact_checksums": {
            "missing.csv": {"size_bytes": 0, "sha256": "0" * 64}
        }
    }), encoding="utf-8")
    verified, failures = verifier.verify_manifest(manifest)
    assert verified == []
    assert failures == ["missing.csv: artifact is missing"]


def test_artifact_verifier_rejects_non_object_json_root(tmp_path):
    manifest = tmp_path / "quickstart_manifest.json"
    manifest.write_text("[]", encoding="utf-8")
    verified, failures = verifier.verify_manifest(manifest)
    assert verified == []
    assert failures == ["manifest root must be a JSON object"]


def test_artifact_verifier_rejects_symlinked_artifact(tmp_path):
    outside = tmp_path.parent / "outside-artifact.txt"
    outside.write_text("not part of the run directory", encoding="utf-8")
    (tmp_path / "linked.txt").symlink_to(outside)
    manifest = tmp_path / "quickstart_manifest.json"
    manifest.write_text(json.dumps({
        "artifact_checksums": {
            "linked.txt": {
                "size_bytes": outside.stat().st_size,
                "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
            }
        }
    }), encoding="utf-8")
    verified, failures = verifier.verify_manifest(manifest)
    assert verified == []
    assert failures == ["linked.txt: artifact must be a regular file beside the manifest"]

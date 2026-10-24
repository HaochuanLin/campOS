import hashlib
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUICKSTART_PATH = ROOT / "src" / "campos" / "quickstart.py"
SPEC = importlib.util.spec_from_file_location("campos_quickstart_manifest", QUICKSTART_PATH)
assert SPEC is not None and SPEC.loader is not None
quickstart = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quickstart)


def test_artifact_checksums_are_stable_and_exclude_self_referential_files(tmp_path):
    csv_file = tmp_path / "results.csv"
    csv_file.write_bytes(b"site,score\nA,0.5\n")
    (tmp_path / "index.html").write_text("report", encoding="utf-8")
    (tmp_path / "quickstart_manifest.json").write_text("{}", encoding="utf-8")

    first = quickstart.artifact_checksums(tmp_path)
    second = quickstart.artifact_checksums(tmp_path)

    assert first == second
    assert list(first) == ["results.csv"]
    assert first["results.csv"]["size_bytes"] == csv_file.stat().st_size
    assert first["results.csv"]["sha256"] == hashlib.sha256(csv_file.read_bytes()).hexdigest()

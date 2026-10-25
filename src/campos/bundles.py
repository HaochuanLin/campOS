"""Small helpers for building portable campOS ZIP artifacts."""
from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping, Sequence
import io
import zipfile


def zip_bytes(artifacts: Mapping[str, bytes]) -> bytes:
    """Return a ZIP containing named byte payloads, rejecting unsafe archive paths."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(artifacts.items()):
            path = Path(name)
            if path.is_absolute() or len(path.parts) != 1 or name in {"", ".", ".."} or "\\" in name:
                raise ValueError(f"unsafe ZIP artifact name: {name!r}")
            if not isinstance(payload, bytes):
                raise TypeError(f"ZIP artifact {name!r} must be bytes")
            archive.writestr(name, payload)
    return buffer.getvalue()


def read_template_payloads(template_dir: Path, filenames: Sequence[str]) -> tuple[dict[str, bytes], list[str]]:
    """Read available template files and return missing names separately for clear UI warnings."""
    payloads: dict[str, bytes] = {}
    missing: list[str] = []
    for filename in filenames:
        path = Path(filename)
        if path.is_absolute() or len(path.parts) != 1 or filename in {"", ".", ".."} or "\\" in filename:
            raise ValueError(f"unsafe template filename: {filename!r}")
        source = template_dir / filename
        if source.is_file():
            payloads[filename] = source.read_bytes()
        else:
            missing.append(filename)
    return payloads, missing

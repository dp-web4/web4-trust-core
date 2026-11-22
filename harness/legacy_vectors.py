"""Verify the original released vector bytes without requiring Git at runtime."""
import hashlib
import json
from pathlib import Path


def verify_legacy_vectors(root: Path, manifest_path: Path) -> list[str]:
    """Return explicit failures; extra new vectors are permitted, old bytes are not changed."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"manifest unreadable: {error}"]
    if not isinstance(manifest, dict) or not manifest:
        return ["legacy vector manifest is empty or malformed"]
    failures = []
    vectors = (root / "vectors").resolve()
    for relative, expected in sorted(manifest.items()):
        if not isinstance(relative, str) or not relative.startswith("vectors/") or relative.startswith("vectors/r1/"):
            failures.append(f"invalid legacy path: {relative!r}")
            continue
        path = root / relative
        try:
            if not path.resolve().is_relative_to(vectors):
                failures.append(f"legacy path escapes vectors: {relative}")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            failures.append(f"legacy vector unavailable: {relative}: {error}")
            continue
        if actual != expected:
            failures.append(f"legacy vector differs: {relative}")
    return failures

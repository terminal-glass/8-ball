from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator

from eight_ball.config import load_json, load_yaml, write_json
from eight_ball.paths import CONFIG_DIR, REPO_ROOT, SCHEMAS_DIR

MANIFEST_SCHEMA = "terminal-glass.8-ball.component-release/1"
DEFAULT_MANIFEST = REPO_ROOT / "install" / "releases" / "v0.8.0" / "component-release-manifest.json"
DEFAULT_DOC = REPO_ROOT / "docs" / "component-release-manifest.md"
UNSIGNED = {
    "status": "unsigned",
    "algorithm": None,
    "public_key_id": None,
    "value": None,
}


class ReleaseVerificationError(Exception):
    """Raised when a component digest or signature does not verify."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def composite_sha256(artifacts: list[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for artifact in artifacts:
        digest.update(artifact["path"].encode())
        digest.update(b"\0")
        digest.update(artifact["sha256"].encode())
        digest.update(b"\n")
    return digest.hexdigest()


def build_manifest(root: Path | None = None, *, source_path: Path | None = None) -> dict[str, Any]:
    root = root or REPO_ROOT
    source = load_yaml(source_path or CONFIG_DIR / "release-components.yaml")
    components: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for row in source["components"]:
        artifacts = []
        for rel in row["paths"]:
            file_path = root / rel
            if not file_path.is_file():
                raise FileNotFoundError(rel)
            artifacts.append({"path": rel, "sha256": file_sha256(file_path)})
        component = {
            "id": row["id"],
            "version": row["version"],
            "platform": row["platform"],
            "role": row["role"],
            "required": row["required"],
            "dependencies": list(row["dependencies"]),
            "source": {
                "repository": "terminal-glass/8-ball",
                "path": row["entry_point"] or row["paths"][0],
            },
            "artifacts": artifacts,
            "sha256": composite_sha256(artifacts),
            "signature": dict(UNSIGNED),
            "entry_point": row["entry_point"],
            "execution_order": list(row["execution_order"]),
            "experimental": row["experimental"],
            "letter_suffix": row["letter_suffix"],
            "not_in_default_chain": row["not_in_default_chain"],
            "hardware_execution": row["hardware_execution"],
            "repository_tests": row["repository_tests"],
            "auto_installs_models": False,
        }
        components.append(component)
        by_id[component["id"]] = component

    entry_points = []
    for row in source["entry_points"]:
        component = by_id[row["component_id"]]
        entry_points.append(
            {
                "consumer": row["consumer"],
                "os": row["os"],
                "lane": row["lane"],
                "component_id": row["component_id"],
                "entry_point": component["entry_point"],
                "execution_order": list(component["execution_order"]),
                "hardware_execution": component["hardware_execution"],
                "repository_tests": component["repository_tests"],
                "sha256": component["sha256"],
            }
        )

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "installer_suite_version": source["installer_suite_version"],
        "catalog_version": source["catalog_version"],
        "catalog_version_independent": True,
        "size_unit_policy": "decimal",
        "signature_policy": {
            "algorithm_when_signed": "ed25519",
            "unsigned_allowed": True,
            "note": (
                "sha256 mismatch is rejected. A signed component with a bad or "
                "missing signature is rejected. Published components stay unsigned "
                "until a release key is chosen."
            ),
        },
        "auto_install_on_catalog_refresh": False,
        "default_execution_order": [
            "trial-install.sh",
            "8.1.sh",
            "8.2.sh",
            "8.3.sh",
        ],
        "components": components,
        "entry_points": entry_points,
    }
    errors = schema_errors(manifest)
    if errors:
        raise ReleaseVerificationError("; ".join(errors))
    return manifest


def schema_errors(manifest: dict[str, Any]) -> list[str]:
    schema = load_json(SCHEMAS_DIR / "component-release-manifest.schema.json")
    validator = Draft202012Validator(schema)
    return [
        error.message
        for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path))
    ]


def verify_manifest(
    manifest: dict[str, Any],
    *,
    root: Path | None = None,
    public_keys: dict[str, bytes] | None = None,
    unsigned_allowed: bool | None = None,
) -> list[str]:
    """Recompute hashes and signatures. Return failure reasons. Empty means verified."""
    root = root or REPO_ROOT
    public_keys = public_keys or {}
    failures: list[str] = []
    failures.extend(schema_errors(manifest))
    if manifest.get("auto_install_on_catalog_refresh") is not False:
        failures.append("catalog refresh must not auto-install models")
    allowed = manifest.get("signature_policy", {}).get("unsigned_allowed", False)
    if unsigned_allowed is not None:
        allowed = unsigned_allowed
    for component in manifest.get("components", []):
        failures.extend(
            _verify_component(
                component,
                root=root,
                public_keys=public_keys,
                unsigned_allowed=allowed,
            )
        )
    return failures


def _verify_component(
    component: dict[str, Any],
    *,
    root: Path,
    public_keys: dict[str, bytes],
    unsigned_allowed: bool,
) -> list[str]:
    failures: list[str] = []
    component_id = component.get("id", "?")
    artifacts = []
    for artifact in component.get("artifacts", []):
        path = root / artifact["path"]
        if not path.is_file():
            failures.append(f"{component_id}: missing {artifact['path']}")
            continue
        actual = file_sha256(path)
        if actual != artifact.get("sha256"):
            failures.append(f"{component_id}: sha256 mismatch for {artifact['path']}")
        artifacts.append({"path": artifact["path"], "sha256": actual})
    if artifacts and composite_sha256(component.get("artifacts", [])) != component.get("sha256"):
        failures.append(f"{component_id}: composite sha256 mismatch")
    signature = component.get("signature") or {}
    status = signature.get("status")
    if status == "unsigned":
        if signature.get("value") not in (None, ""):
            failures.append(f"{component_id}: unsigned component carries a signature value")
        if not unsigned_allowed:
            failures.append(f"{component_id}: unsigned components are not allowed")
        return failures
    if status != "signed":
        failures.append(f"{component_id}: unknown signature status {status}")
        return failures
    if signature.get("algorithm") != "ed25519":
        failures.append(f"{component_id}: signature algorithm must be ed25519")
        return failures
    key_id = signature.get("public_key_id")
    raw_key = public_keys.get(key_id or "")
    if raw_key is None:
        failures.append(f"{component_id}: unknown signing key {key_id}")
        return failures
    try:
        signature_bytes = bytes.fromhex(signature.get("value") or "")
        Ed25519PublicKey.from_public_bytes(raw_key).verify(
            signature_bytes,
            str(component.get("sha256")).encode(),
        )
    except (InvalidSignature, ValueError):
        failures.append(f"{component_id}: signature verification failed")
    return failures


def render_entry_point_doc(manifest: dict[str, Any]) -> str:
    lines = [
        "<!-- Generated from config/release-components.yaml by eight_ball.manager.release. Do not edit by hand. -->",
        "",
        "# Component release manifest",
        "",
        "Customer installers consume `install/releases/v0.8.0/component-release-manifest.json`.",
        (
            "Catalog version "
            f"`{manifest['catalog_version']}` is independent of installer suite "
            f"`{manifest['installer_suite_version']}`."
        ),
        "A catalog refresh does not install models.",
        "The default chain remains `trial-install.sh`, `8.1.sh`, `8.2.sh`, `8.3.sh`.",
        "Experimental scripts keep a letter suffix until they are assigned a permanent stage.",
        "Hardware execution for every lane below is untested in this change.",
        "Windows hardware execution is untested, and `pwsh` smoke steps are not run here.",
        "",
        "Integrity is sha256 of each artifact plus a composite sha256.",
        "Signed components use ed25519 over that composite digest.",
        "Published components are unsigned until a release key is chosen.",
        "A sha256 mismatch or a bad signature is rejected.",
        "This manifest does not replace the existing v0.8.0 runtime-bundle pin.",
        "",
        "| Consumer | OS | Lane | Entry point | Component | Hardware |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in manifest["entry_points"]:
        lines.append(
            "| {consumer} | {os} | {lane} | `{entry}` | `{component}` | {hardware} |".format(
                consumer=row["consumer"],
                os=row["os"],
                lane=row["lane"],
                entry=row["entry_point"],
                component=row["component_id"],
                hardware=row["hardware_execution"],
            )
        )
    lines.extend(
        [
            "",
            "## Experimental manager",
            "",
            "`install/shared/8.4a-model-manager.sh` is optional, letter-suffixed, and outside the default chain.",
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(root: Path | None = None) -> dict[str, Any]:
    manifest = build_manifest(root)
    write_json(DEFAULT_MANIFEST, manifest)
    DEFAULT_DOC.write_text(render_entry_point_doc(manifest), encoding="utf-8")
    return manifest

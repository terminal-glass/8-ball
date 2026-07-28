from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup

from eight_ball.normalize.parse import (
    parse_context_length,
    parse_parameter_label,
    parse_size_text_to_bytes,
)

_FAMILY_LINK_RE = re.compile(r"^/library/([^/:]+)$")
_TAG_LINK_RE = re.compile(r"^/library/([^:]+):([^/]+)$")
_QUANT_SUFFIXES = (
    "mxfp8",
    "nvfp4",
    "bf16",
    "fp16",
    "f16",
    "fp4",
    "q8_0",
    "q8",
    "q6_K",
    "q5_K_M",
    "q5_K_S",
    "q5_1",
    "q5_0",
    "q4_K_M",
    "q4_K_S",
    "q4_1",
    "q4_0",
    "q3_K_L",
    "q3_K_M",
    "q3_K_S",
    "q2_K",
)


@dataclass
class ParsedFamilyIndexEntry:
    slug: str
    display_name: str | None = None
    description: str | None = None


@dataclass
class ParsedFamilyPage:
    slug: str
    display_name: str | None = None
    description: str | None = None
    source_url: str | None = None
    is_cloud_family: bool = False
    capability_badges: list[str] = field(default_factory=list)


@dataclass
class ParsedTag:
    ollama_identifier: str
    family_slug: str
    tag_suffix: str
    digest: str | None = None
    is_latest: bool = False
    download_size_text: str | None = None
    download_size_bytes: int | None = None
    context_length_text: str | None = None
    context_window_tokens: int | None = None
    input_capabilities: list[str] = field(default_factory=list)
    quantization: str | None = None
    parameter_label: str | None = None
    parameter_count: int | None = None
    alias_target: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ollama_identifier": self.ollama_identifier,
            "family_slug": self.family_slug,
            "tag_suffix": self.tag_suffix,
            "digest": self.digest,
            "is_latest": self.is_latest,
            "download_size_text": self.download_size_text,
            "download_size_bytes": self.download_size_bytes,
            "context_length_text": self.context_length_text,
            "context_window_tokens": self.context_window_tokens,
            "input_capabilities": self.input_capabilities,
            "quantization": self.quantization,
            "parameter_label": self.parameter_label,
            "parameter_count": self.parameter_count,
        }


def extract_quantization(tag_suffix: str) -> str | None:
    lowered = tag_suffix.lower()
    for suffix in _QUANT_SUFFIXES:
        suffix_lower = suffix.lower()
        if lowered.endswith((f"-{suffix_lower}", suffix_lower)):
            return suffix
    return None


def extract_parameter_label(tag_suffix: str) -> str | None:
    match = re.match(r"^(\d+(?:\.\d+)?[kmbt])(?:$|[-_])", tag_suffix, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def _row_text_for_link(link) -> str:
    node = link
    for _ in range(8):
        if node is None:
            break
        text = node.get_text(" • ", strip=True)
        if "context window" in text and ("MB" in text or "GB" in text or "KB" in text):
            return text
        node = node.parent
    return link.get_text(" • ", strip=True)


def _parse_tag_row_text(ollama_id: str, row_text: str) -> dict[str, Any]:
    parts = [part.strip() for part in row_text.split("•") if part.strip()]
    payload: dict[str, Any] = {
        "digest": None,
        "is_latest": False,
        "download_size_text": None,
        "context_length_text": None,
        "input_capabilities": [],
    }
    for part in parts:
        if part == ollama_id:
            continue
        if part.lower() == "latest":
            payload["is_latest"] = True
            continue
        if re.fullmatch(r"[a-f0-9]{12}", part):
            payload["digest"] = part
            continue
        if re.search(r"\d+(?:\.\d+)?\s*(?:KB|MB|GB|TB)", part, re.IGNORECASE):
            payload["download_size_text"] = part.replace(" ", "")
            continue
        if "context window" in part.lower():
            payload["context_length_text"] = part
            continue
        if "input" in part.lower() or part in {"Text", "Image", "Audio", "Video"}:
            payload["input_capabilities"].append(part)
    return payload


def parse_family_tags_page(html: str, family_slug: str) -> list[ParsedTag]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    tags: list[ParsedTag] = []

    for link in soup.find_all("a", href=True):
        match = _TAG_LINK_RE.match(link["href"])
        if not match or match.group(1) != family_slug:
            continue
        tag_suffix = match.group(2)
        ollama_id = f"{family_slug}:{tag_suffix}"
        if ollama_id in seen:
            continue
        seen.add(ollama_id)

        row = _parse_tag_row_text(ollama_id, _row_text_for_link(link))
        param_label = extract_parameter_label(tag_suffix)
        param_count, param_unit = parse_parameter_label(param_label)
        tags.append(
            ParsedTag(
                ollama_identifier=ollama_id,
                family_slug=family_slug,
                tag_suffix=tag_suffix,
                digest=row["digest"],
                is_latest=bool(row["is_latest"] or tag_suffix == "latest"),
                download_size_text=row["download_size_text"],
                download_size_bytes=parse_size_text_to_bytes(row["download_size_text"]),
                context_length_text=row["context_length_text"],
                context_window_tokens=parse_context_length(row["context_length_text"]),
                input_capabilities=row["input_capabilities"],
                quantization=extract_quantization(tag_suffix),
                parameter_label=param_unit or param_label,
                parameter_count=param_count,
            )
        )

    tags.sort(key=lambda item: item.ollama_identifier)
    apply_alias_targets(tags)
    return tags


def parse_family_page(html: str, family_slug: str) -> ParsedFamilyPage:
    soup = BeautifulSoup(html, "html.parser")
    display_name = None
    title = soup.find("title")
    if title:
        display_name = title.get_text(strip=True).split("|")[0].strip() or None
    heading = soup.find("h1")
    if heading:
        heading_text = heading.get_text(strip=True)
        if heading_text and heading_text != family_slug:
            display_name = heading_text

    description = None
    for node in soup.find_all(["p", "div"]):
        text = node.get_text(" ", strip=True)
        if len(text) > 40 and family_slug in text.lower() and "download" not in text.lower()[:20]:
            description = text[:500]
            break

    capability_badges: list[str] = []
    for span in soup.find_all("span"):
        label = span.get_text(strip=True).lower()
        if label in {"vision", "tools", "thinking", "embedding", "cloud"}:
            capability_badges.append(label)
    is_cloud_family = "cloud" in capability_badges or "cloud" in html.lower()

    return ParsedFamilyPage(
        slug=family_slug,
        display_name=display_name or family_slug,
        description=description,
        source_url=f"https://ollama.com/library/{family_slug}",
        is_cloud_family=is_cloud_family,
        capability_badges=sorted(set(capability_badges)),
    )


def apply_alias_targets(tags: list[ParsedTag]) -> None:
    """Mark tags that share a digest as aliases of the preferred target tag."""
    by_digest: dict[str, list[ParsedTag]] = {}
    for tag in tags:
        if tag.digest:
            by_digest.setdefault(tag.digest, []).append(tag)

    for digest_tags in by_digest.values():
        if len(digest_tags) < 2:
            continue
        preferred = next((tag for tag in digest_tags if tag.is_latest), None)
        if preferred is None:
            preferred = min(digest_tags, key=lambda item: len(item.tag_suffix))
        for tag in digest_tags:
            if tag.ollama_identifier != preferred.ollama_identifier:
                tag.alias_target = preferred.ollama_identifier


def parse_library_index(html: str) -> list[ParsedFamilyIndexEntry]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    entries: list[ParsedFamilyIndexEntry] = []

    for link in soup.find_all("a", href=True):
        match = _FAMILY_LINK_RE.match(link["href"])
        if not match:
            continue
        slug = match.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        text = link.get_text(" ", strip=True)
        display_name = text.split(slug, 1)[0].strip() if text.startswith(slug) else slug
        description = text[len(slug) :].strip() if text.startswith(slug) else text
        entries.append(
            ParsedFamilyIndexEntry(
                slug=slug,
                display_name=display_name or slug,
                description=description or None,
            )
        )

    entries.sort(key=lambda item: item.slug)
    return entries

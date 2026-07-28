from __future__ import annotations

from eight_ball.generate.deployments import stable_deployment_id
from eight_ball.normalize.parse import parse_context_length, parse_size_text_to_bytes


def test_parse_size_decimal_gb():
    assert parse_size_text_to_bytes("4.7GB") == 4_700_000_000


def test_parse_context_length():
    assert parse_context_length("32K") == 32_000


def test_stable_deployment_id_is_deterministic():
    a = stable_deployment_id("llama3__8b", "gpu-midrange", "interactive")
    b = stable_deployment_id("llama3__8b", "gpu-midrange", "interactive")
    assert a == b
    assert len(a) == 24

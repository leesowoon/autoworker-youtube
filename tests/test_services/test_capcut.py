"""Tests for CapCut project generator."""

import json
from pathlib import Path

from autoworker_youtube.services.capcut import (
    _generate_id,
    _seconds_to_microseconds,
)


class TestCapCutUtils:
    def test_generate_id(self):
        id1 = _generate_id()
        id2 = _generate_id()
        assert len(id1) == 24
        assert id1 != id2

    def test_seconds_to_microseconds(self):
        assert _seconds_to_microseconds(1.0) == 1_000_000
        assert _seconds_to_microseconds(0.5) == 500_000
        assert _seconds_to_microseconds(10.0) == 10_000_000

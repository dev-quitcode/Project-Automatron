"""Tests for Docker engine (mocked)."""

import pytest

from orchestrator.docker_engine.port_allocator import PortAllocator


def test_port_free_check():
    """Test that _is_port_free works for high ports."""
    allocator = PortAllocator(start=49000, end=49010)
    # Very high ports should generally be free
    assert allocator._is_port_free(49999) is True

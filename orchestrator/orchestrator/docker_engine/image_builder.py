"""Golden Image builder utility."""

from __future__ import annotations

import logging
from pathlib import Path

import docker
from docker.errors import DockerException

logger = logging.getLogger(__name__)

GOLDEN_IMAGE_DOCKERFILE = Path(__file__).parent.parent.parent.parent / "docker" / "golden-image"


def build_golden_image(tag: str = "automatron/golden:latest") -> str:
    """Build the Golden Image from the Dockerfile.

    Args:
        tag: Docker image tag

    Returns:
        Image ID
    """
    client = docker.from_env()

    logger.info("Building Golden Image: %s from %s", tag, GOLDEN_IMAGE_DOCKERFILE)

    try:
        image, build_logs = client.images.build(
            path=str(GOLDEN_IMAGE_DOCKERFILE),
            tag=tag,
            rm=True,
            forcerm=True,
        )

        for log in build_logs:
            if "stream" in log:
                logger.debug(log["stream"].strip())

        logger.info("Golden Image built: %s (id=%s)", tag, image.id[:12])
        return image.id

    except DockerException as e:
        logger.error("Failed to build Golden Image: %s", e)
        raise

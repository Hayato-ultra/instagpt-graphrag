"""Video processing optimization with adaptive frame sampling (TODO #42).

Reduces computational cost by sampling frames intelligently.
"""
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class FrameSamplingConfig:
    """Configuration for adaptive frame sampling."""
    min_frames: int = 3
    max_frames: int = 15
    interval_seconds: float = 2.0
    content_threshold: float = 0.1  # Min content change to keep frame


def _frame_has_content(frame_data: bytes, prev_frame_data: bytes | None = None) -> bool:
    """Check if frame has meaningful content (not just black/empty).

    Uses simple heuristic: frame should have non-zero pixels.
    """
    if not frame_data:
        return False

    # Check if frame has enough non-zero bytes (content)
    non_zero = sum(1 for b in frame_data[:1000] if b != 0)
    return non_zero > len(frame_data[:1000]) * 0.05


def _frames_are_similar(frame1: bytes, frame2: bytes, threshold: float = 0.9) -> bool:
    """Check if two frames are too similar (skip duplicate)."""
    if not frame1 or not frame2:
        return False

    # Compare first N bytes as sample
    sample_size = min(500, len(frame1), len(frame2))
    if sample_size == 0:
        return False

    matches = sum(1 for a, b in zip(frame1[:sample_size], frame2[:sample_size]) if a == b)
    return matches / sample_size > threshold


def calculate_optimal_interval(
    video_duration_seconds: float,
    target_frames: int = 10,
) -> float:
    """Calculate optimal frame sampling interval based on video length.

    Args:
        video_duration_seconds: total video duration.
        target_frames: desired number of frames.

    Returns:
        Interval in seconds between frames.
    """
    if video_duration_seconds <= 0:
        return 2.0

    interval = video_duration_seconds / target_frames
    # Clamp between 0.5s and 10s
    return max(0.5, min(10.0, interval))


def select_key_frames(
    frames: list[bytes],
    config: FrameSamplingConfig | None = None,
) -> list[int]:
    """Select key frames from extracted frames (TODO #42).

    Args:
        frames: list of frame data (bytes).
        config: sampling configuration.

    Returns:
        Indices of selected key frames.
    """
    cfg = config or FrameSamplingConfig()

    if not frames:
        return []

    selected = []
    prev_frame = None

    for i, frame in enumerate(frames):
        # Skip empty frames
        if not _frame_has_content(frame):
            continue

        # Skip if too similar to previous selected frame
        if prev_frame and _frames_are_similar(frame, prev_frame):
            continue

        selected.append(i)
        prev_frame = frame

        # Stop if we've reached max frames
        if len(selected) >= cfg.max_frames:
            break

    # Ensure minimum frames
    if len(selected) < cfg.min_frames and frames:
        # Select evenly spaced frames
        step = max(1, len(frames) // cfg.min_frames)
        selected = list(range(0, len(frames), step))[:cfg.min_frames]

    logger.debug(f"Frame selection: {len(frames)} total → {len(selected)} key frames")
    return selected

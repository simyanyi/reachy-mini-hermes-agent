"""Configuration for Reachy Mini integration."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReachyConfig:
    """Configuration for connecting to Reachy Mini."""

    connection_mode: str = "network"  # "auto", "localhost_only", "network"
    media_backend: str = "default"  # "no_media", "default", or "gstreamer"
    dashboard_url: str = "http://localhost:8000"  # Reachy Mini dashboard for REST API
    emotions_dataset: str = "pollen-robotics/reachy-mini-emotions-library"
    dances_dataset: str = "pollen-robotics/reachy-mini-dances-library"
    capture_dir: Path = field(default_factory=lambda: Path.home() / ".hermes" / "reachy-captures")

    # Movement defaults
    default_duration: float = 1.0
    antenna_duration: float = 0.5

    # Safety limits (degrees)
    max_roll: float = 30.0
    max_pitch: float = 30.0
    max_yaw: float = 45.0

    def __post_init__(self):
        self.capture_dir.mkdir(parents=True, exist_ok=True)


_config: ReachyConfig | None = None


def get_config() -> ReachyConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = ReachyConfig()
    return _config


def set_config(config: ReachyConfig) -> None:
    """Set the global config instance."""
    global _config
    _config = config

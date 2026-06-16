"""Configuration for Reachy Mini Hermes interface."""

from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass
class Config:
    """Configuration for the Reachy Mini interface."""

    # Hermes Agent
    hermes_home: Path = field(default_factory=lambda: Path.home() / ".hermes")
    model: str = "anthropic/claude-opus-4.6"

    # Reachy Mini connection
    reachy_connection_mode: str = "network"  # "auto", "localhost_only", "network"
    reachy_media_backend: str = "default"  # "no_media", "default", or "gstreamer"
    reachy_dashboard_url: str = "http://192.168.50.116:8000"

    # Speech-to-text
    stt_backend: str = "whisper"  # "whisper", "faster-whisper", "openai"
    whisper_model: str = "base"  # "tiny", "base", "small", "medium", "large"
    openai_api_key: str | None = None

    # Text-to-speech
    tts_voice: str | None = None

    # Audio settings
    audio_device: str | None = None
    sample_rate: int = 16000
    silence_threshold: float = 0.01
    silence_duration: float = 1.5
    max_recording_duration: float = 30.0

    # Behavior
    wake_word: str | None = "hey reachy"
    play_emotions: bool = True
    idle_animations: bool = True
    standalone_mode: bool = False  # Run without AI (echo mode for testing)

    # Paths
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".hermes" / "reachy-cache")

    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")

    @property
    def hermes_agent_path(self) -> Path:
        return self.hermes_home / "hermes-agent"


def load_config() -> Config:
    """Load configuration from environment and defaults."""
    return Config(
        hermes_home=Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))),
        model=os.environ.get("HERMES_MODEL", "anthropic/claude-opus-4.6"),
        stt_backend=os.environ.get("STT_BACKEND", "whisper"),
        whisper_model=os.environ.get("WHISPER_MODEL", "base"),
        wake_word=os.environ.get("WAKE_WORD", "hey reachy"),
        reachy_dashboard_url=os.environ.get("REACHY_DASHBOARD_URL", "http://192.168.50.116:8000"),
        reachy_media_backend=os.environ.get("REACHY_MEDIA_BACKEND", "default"),
    )

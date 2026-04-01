"""Bridge between Hermes Agent and Reachy Mini SDK."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .reachy_config import get_config, ReachyConfig

if TYPE_CHECKING:
    from reachy_mini import ReachyMini

logger = logging.getLogger(__name__)


class ReachyBridge:
    """Manages connection and communication with Reachy Mini robot.

    Used as a singleton via get_bridge(). Shared between the hermes plugin
    tools (AI-driven commands) and the voice interface (system animations).
    """

    def __init__(self, config: ReachyConfig | None = None):
        self.config = config or get_config()
        self._mini: ReachyMini | None = None
        self._connected = False
        self._animation_lock = asyncio.Lock()

    @property
    def mini(self) -> ReachyMini | None:
        """Direct access to the ReachyMini instance for system animations."""
        return self._mini

    @property
    def is_connected(self) -> bool:
        return self._connected and self._mini is not None

    def connect(self, connection_mode: str | None = None) -> dict:
        """Connect to the Reachy Mini robot."""
        if self.is_connected:
            return {"status": "already_connected"}

        try:
            from reachy_mini import ReachyMini

            mode = connection_mode or self.config.connection_mode
            kwargs = {"media_backend": self.config.media_backend}
            if mode != "auto":
                kwargs["connection_mode"] = mode

            self._mini = ReachyMini(**kwargs)
            self._mini.__enter__()
            self._connected = True

            logger.info("Connected to Reachy Mini")
            return {"status": "connected", "mode": mode}

        except ImportError:
            return {"status": "error", "message": "reachy-mini package not installed"}
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return {"status": "error", "message": str(e)}

    def disconnect(self) -> dict:
        """Disconnect from the Reachy Mini robot."""
        if not self.is_connected:
            return {"status": "not_connected"}

        try:
            self._mini.__exit__(None, None, None)
            self._mini = None
            self._connected = False

            logger.info("Disconnected from Reachy Mini")
            return {"status": "disconnected"}

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            return {"status": "error", "message": str(e)}

    def move_head(
        self,
        z: float = 0,
        roll: float = 0,
        pitch: float = 0,
        yaw: float = 0,
        duration: float | None = None,
    ) -> dict:
        """Move the robot's head to target position."""
        if not self.is_connected:
            return {"status": "error", "message": "Not connected to robot"}

        try:
            from reachy_mini.utils import create_head_pose

            roll = max(-self.config.max_roll, min(self.config.max_roll, roll))
            pitch = max(-self.config.max_pitch, min(self.config.max_pitch, pitch))
            yaw = max(-self.config.max_yaw, min(self.config.max_yaw, yaw))

            dur = duration or self.config.default_duration

            self._mini.goto_target(
                head=create_head_pose(z=z, roll=roll, pitch=pitch, yaw=yaw, degrees=True, mm=True),
                duration=dur,
            )

            return {
                "status": "success",
                "position": {"z": z, "roll": roll, "pitch": pitch, "yaw": yaw},
                "duration": dur,
            }

        except Exception as e:
            logger.error(f"Failed to move head: {e}")
            return {"status": "error", "message": str(e)}

    def move_antennas(
        self,
        left: float = 0,
        right: float = 0,
        duration: float | None = None,
    ) -> dict:
        """Move the robot's antennas. Angles are in degrees, converted to radians for the SDK."""
        if not self.is_connected:
            return {"status": "error", "message": "Not connected to robot"}

        try:
            import math
            left_rad = math.radians(left)
            right_rad = math.radians(right)

            self._mini.set_target_antenna_joint_positions([left_rad, right_rad])

            return {
                "status": "success",
                "antennas": {"left": left, "right": right},
            }

        except Exception as e:
            logger.error(f"Failed to move antennas: {e}")
            return {"status": "error", "message": str(e)}

    def play_emotion(self, emotion: str) -> dict:
        """Play an emotion animation via the dashboard REST API."""
        if not self.is_connected:
            return {"status": "error", "message": "Not connected to robot"}

        try:
            import httpx
            url = (
                f"{self.config.dashboard_url}/api/move/play/"
                f"recorded-move-dataset/{self.config.emotions_dataset}/{emotion}"
            )
            resp = httpx.post(url, timeout=10.0)
            resp.raise_for_status()
            return {"status": "success", "emotion": emotion}

        except Exception as e:
            logger.error(f"Failed to play emotion: {e}")
            return {"status": "error", "message": str(e)}

    def dance(self, dance_name: str) -> dict:
        """Trigger a dance routine via the dashboard REST API."""
        if not self.is_connected:
            return {"status": "error", "message": "Not connected to robot"}

        try:
            import httpx
            url = (
                f"{self.config.dashboard_url}/api/move/play/"
                f"recorded-move-dataset/{self.config.dances_dataset}/{dance_name}"
            )
            resp = httpx.post(url, timeout=10.0)
            resp.raise_for_status()
            return {"status": "success", "dance": dance_name}

        except Exception as e:
            logger.error(f"Failed to dance: {e}")
            return {"status": "error", "message": str(e)}

    def capture_image(self) -> dict:
        """Capture an image from the robot's camera."""
        if not self.is_connected:
            return {"status": "error", "message": "Not connected to robot"}

        try:
            frame = self._mini.camera.get_frame()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.config.capture_dir / f"capture_{timestamp}.jpg"

            try:
                import cv2
                cv2.imwrite(str(filepath), frame)
            except ImportError:
                if hasattr(frame, "save"):
                    frame.save(filepath)
                else:
                    return {"status": "error", "message": "cv2 not available for saving images"}

            return {"status": "success", "filepath": str(filepath)}

        except Exception as e:
            logger.error(f"Failed to capture image: {e}")
            return {"status": "error", "message": str(e)}

    def say(self, text: str, voice: str | None = None) -> dict:
        """Make the robot speak using TTS."""
        if not self.is_connected:
            return {"status": "error", "message": "Not connected to robot"}

        try:
            kwargs = {"text": text}
            if voice:
                kwargs["voice"] = voice

            self._mini.say(**kwargs)
            return {"status": "success", "text": text}

        except Exception as e:
            logger.error(f"Failed to speak: {e}")
            return {"status": "error", "message": str(e)}

    def get_status(self) -> dict:
        """Get current robot status."""
        return {
            "connected": self.is_connected,
            "config": {
                "connection_mode": self.config.connection_mode,
                "media_backend": self.config.media_backend,
            },
        }


_bridge: ReachyBridge | None = None


def get_bridge() -> ReachyBridge:
    """Get or create the global bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = ReachyBridge()
    return _bridge

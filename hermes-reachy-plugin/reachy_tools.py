"""Hermes tool definitions for Reachy Mini robot control."""

import json

from .reachy_bridge import get_bridge

TOOLSET = "reachy"
EMOJI = "🤖"


def _check_reachy_available() -> bool:
    """Check if the reachy_mini SDK is importable."""
    try:
        import reachy_mini  # noqa: F401
        return True
    except ImportError:
        return False


# -- Handlers (return JSON strings as required by hermes registry) ----------


def _handle_connect(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().connect(args.get("connection_mode", "auto")))


def _handle_disconnect(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().disconnect())


def _handle_move_head(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().move_head(
        z=args.get("z", 0),
        roll=args.get("roll", 0),
        pitch=args.get("pitch", 0),
        yaw=args.get("yaw", 0),
        duration=args.get("duration"),
    ))


def _handle_move_antennas(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().move_antennas(
        left=args.get("left", 0),
        right=args.get("right", 0),
        duration=args.get("duration"),
    ))


def _handle_play_emotion(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().play_emotion(args["emotion"]))


def _handle_dance(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().dance(args["dance_name"]))


def _handle_capture_image(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().capture_image())


def _handle_say(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().say(
        text=args["text"],
        voice=args.get("voice"),
    ))


def _handle_status(args: dict, **kwargs) -> str:
    return json.dumps(get_bridge().get_status())


# -- Schemas (OpenAI function-calling format) --------------------------------


REACHY_CONNECT_SCHEMA = {
    "name": "reachy_connect",
    "description": "Connect to the Reachy Mini robot.",
    "parameters": {
        "type": "object",
        "properties": {
            "connection_mode": {
                "type": "string",
                "enum": ["auto", "localhost_only", "network"],
                "description": "Connection mode (default: auto).",
            },
        },
    },
}

REACHY_DISCONNECT_SCHEMA = {
    "name": "reachy_disconnect",
    "description": "Disconnect from the Reachy Mini robot.",
    "parameters": {"type": "object", "properties": {}},
}

REACHY_MOVE_HEAD_SCHEMA = {
    "name": "reachy_move_head",
    "description": (
        "Move the Reachy Mini robot's head to a target position. "
        "Angles are in degrees, clamped to safety limits (roll/pitch: +-30, yaw: +-45)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "z": {"type": "number", "description": "Vertical position in mm (default: 0)."},
            "roll": {"type": "number", "description": "Roll angle in degrees, -30 to 30 (default: 0)."},
            "pitch": {"type": "number", "description": "Pitch angle in degrees, -30 to 30 (default: 0)."},
            "yaw": {"type": "number", "description": "Yaw angle in degrees, -45 to 45 (default: 0)."},
            "duration": {"type": "number", "description": "Movement duration in seconds (default: 1.0)."},
        },
    },
}

REACHY_MOVE_ANTENNAS_SCHEMA = {
    "name": "reachy_move_antennas",
    "description": "Move the Reachy Mini robot's antennas (lobster claws).",
    "parameters": {
        "type": "object",
        "properties": {
            "left": {"type": "number", "description": "Left antenna angle in degrees (default: 0)."},
            "right": {"type": "number", "description": "Right antenna angle in degrees (default: 0)."},
            "duration": {"type": "number", "description": "Movement duration in seconds (default: 0.5)."},
        },
    },
}

REACHY_PLAY_EMOTION_SCHEMA = {
    "name": "reachy_play_emotion",
    "description": (
        "Play a predefined emotion animation on the Reachy Mini robot. "
        "Examples: cheerful1, sad1, surprised1, curious1, laughing1, thoughtful1, "
        "welcoming1, scared1, proud1, confused1, shy1, enthusiastic1, grateful1."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "emotion": {
                "type": "string",
                "description": "Name of the emotion animation to play.",
            },
        },
        "required": ["emotion"],
    },
}

REACHY_DANCE_SCHEMA = {
    "name": "reachy_dance",
    "description": "Trigger a dance routine on the Reachy Mini robot.",
    "parameters": {
        "type": "object",
        "properties": {
            "dance_name": {
                "type": "string",
                "description": "Name of the dance routine to perform.",
            },
        },
        "required": ["dance_name"],
    },
}

REACHY_CAPTURE_IMAGE_SCHEMA = {
    "name": "reachy_capture_image",
    "description": "Capture an image from the Reachy Mini robot's camera.",
    "parameters": {"type": "object", "properties": {}},
}

REACHY_SAY_SCHEMA = {
    "name": "reachy_say",
    "description": (
        "Make the Reachy Mini robot speak using its built-in TTS. "
        "Use this only for short utterances or sound effects, not for main conversation responses."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to speak."},
            "voice": {"type": "string", "description": "Voice to use (optional)."},
        },
        "required": ["text"],
    },
}

REACHY_STATUS_SCHEMA = {
    "name": "reachy_status",
    "description": "Get the current connection status and configuration of the Reachy Mini robot.",
    "parameters": {"type": "object", "properties": {}},
}


# -- Registration table (used by __init__.py) --------------------------------

TOOL_DEFINITIONS = [
    {"schema": REACHY_CONNECT_SCHEMA, "handler": _handle_connect},
    {"schema": REACHY_DISCONNECT_SCHEMA, "handler": _handle_disconnect},
    {"schema": REACHY_MOVE_HEAD_SCHEMA, "handler": _handle_move_head},
    {"schema": REACHY_MOVE_ANTENNAS_SCHEMA, "handler": _handle_move_antennas},
    {"schema": REACHY_PLAY_EMOTION_SCHEMA, "handler": _handle_play_emotion},
    {"schema": REACHY_DANCE_SCHEMA, "handler": _handle_dance},
    {"schema": REACHY_CAPTURE_IMAGE_SCHEMA, "handler": _handle_capture_image},
    {"schema": REACHY_SAY_SCHEMA, "handler": _handle_say},
    {"schema": REACHY_STATUS_SCHEMA, "handler": _handle_status},
]

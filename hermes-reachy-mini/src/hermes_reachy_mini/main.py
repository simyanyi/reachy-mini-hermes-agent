"""Main entry point for Reachy Mini Hermes interface."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys

from hermes_reachy_mini.config import Config, load_config
from hermes_reachy_mini.interface import ReachyInterface


def _fix_libstdcpp() -> None:
    """Re-exec with LD_PRELOAD to fix conda GLIBCXX version conflicts.

    Conda's bundled libstdc++.so.6 may lack GLIBCXX_3.4.32 required by
    system libraries (libjack via portaudio via sounddevice). LD_PRELOAD
    must be set before process start; ctypes.CDLL is too late if other
    imports already loaded the wrong version. Re-exec once with the fix.
    """
    if os.environ.get("_HERMES_REACHY_LIBFIX"):
        return
    system_lib = "/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
    if not os.path.exists(system_lib):
        return
    os.environ["LD_PRELOAD"] = system_lib
    os.environ["_HERMES_REACHY_LIBFIX"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Reachy Mini voice interface for Hermes Agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    # Hermes options
    parser.add_argument(
        "--model",
        default="anthropic/claude-opus-4.6",
        help="AI model to use (OpenRouter format)",
    )
    parser.add_argument(
        "--hermes-home",
        default=None,
        help="Path to Hermes home directory (default: ~/.hermes)",
    )

    # Reachy options
    parser.add_argument(
        "--reachy-mode",
        choices=["auto", "localhost_only", "network"],
        default=None,
        help="Reachy Mini connection mode (default: network)",
    )
    parser.add_argument(
        "--media-backend",
        choices=["default", "no_media", "gstreamer"],
        default=None,
        help="Reachy Mini media backend (default: auto-detect)",
    )

    # STT options
    parser.add_argument(
        "--stt",
        choices=["whisper", "faster-whisper", "openai"],
        default="whisper",
        help="Speech-to-text backend",
    )
    parser.add_argument(
        "--whisper-model",
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size",
    )

    # Audio options
    parser.add_argument(
        "--audio-device",
        help="Audio input device name (e.g., 'RODE NT-USB Mini')",
    )

    # Behavior options
    parser.add_argument(
        "--wake-word",
        help="Wake word to activate listening (e.g., 'hey reachy')",
    )
    parser.add_argument(
        "--no-emotions",
        action="store_true",
        help="Disable emotion animations",
    )
    parser.add_argument(
        "--no-idle",
        action="store_true",
        help="Disable idle animations",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Run in standalone mode without AI agent (echo mode for testing)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a quick demo of robot capabilities",
    )

    return parser.parse_args()


def create_config(args: argparse.Namespace) -> Config:
    """Create config from command line arguments."""
    config = load_config()

    config.model = args.model
    if args.hermes_home:
        from pathlib import Path
        config.hermes_home = Path(args.hermes_home)

    if args.reachy_mode:
        config.reachy_connection_mode = args.reachy_mode
    if args.media_backend:
        config.reachy_media_backend = args.media_backend
    config.audio_device = args.audio_device
    config.stt_backend = args.stt
    config.whisper_model = args.whisper_model
    config.wake_word = args.wake_word
    config.play_emotions = not args.no_emotions
    config.idle_animations = not args.no_idle
    config.standalone_mode = args.standalone

    return config


async def run_demo(config: Config) -> int:
    """Run a quick demo of robot capabilities."""
    logging.info("Starting Reachy Mini demo...")

    try:
        from reachy_mini import ReachyMini
        from reachy_mini.utils import create_head_pose
    except ImportError:
        logging.error("reachy-mini package not installed")
        return 1

    reachy = None
    try:
        kwargs = {"media_backend": config.reachy_media_backend}
        if config.reachy_connection_mode != "auto":
            kwargs["connection_mode"] = config.reachy_connection_mode
        reachy = ReachyMini(**kwargs)
        reachy.__enter__()
        logging.info("Connected to Reachy Mini!")

        logging.info("Waking up robot...")
        reachy.wake_up()
        await asyncio.sleep(1.0)

        # Nod yes
        logging.info("Moving head - nodding yes...")
        for _ in range(2):
            reachy.goto_target(head=create_head_pose(roll=0, pitch=10, degrees=True), duration=0.3)
            await asyncio.sleep(0.4)
            reachy.goto_target(head=create_head_pose(roll=0, pitch=-10, degrees=True), duration=0.3)
            await asyncio.sleep(0.4)

        reachy.goto_target(head=create_head_pose(roll=0, pitch=0, degrees=True), duration=0.5)
        await asyncio.sleep(0.6)

        # Shake no
        logging.info("Moving head - shaking no...")
        for _ in range(2):
            reachy.goto_target(head=create_head_pose(roll=10, pitch=0, degrees=True), duration=0.3)
            await asyncio.sleep(0.4)
            reachy.goto_target(head=create_head_pose(roll=-10, pitch=0, degrees=True), duration=0.3)
            await asyncio.sleep(0.4)

        reachy.goto_target(head=create_head_pose(roll=0, pitch=0, degrees=True), duration=0.5)
        await asyncio.sleep(0.6)

        # Move antennas (radians: 0.5 ~ 29 degrees)
        logging.info("Moving antennas...")
        reachy.set_target_antenna_joint_positions([0.5, -0.5])
        await asyncio.sleep(0.5)
        reachy.set_target_antenna_joint_positions([-0.5, 0.5])
        await asyncio.sleep(0.5)
        reachy.set_target_antenna_joint_positions([0.0, 0.0])
        await asyncio.sleep(0.5)

        logging.info("Demo completed successfully!")

    except Exception as e:
        logging.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if reachy:
            reachy.__exit__(None, None, None)

    return 0


async def async_main(interface: ReachyInterface) -> int:
    """Async main function."""

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logging.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        run_task = asyncio.create_task(interface.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [run_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        return 1
    finally:
        await interface.stop()

    return 0


def main() -> None:
    """Main entry point."""
    _fix_libstdcpp()

    args = parse_args()
    setup_logging(args.verbose)

    config = create_config(args)

    if args.demo:
        logging.info("Running Reachy Mini demo")
        exit_code = asyncio.run(run_demo(config))
        sys.exit(exit_code)

    if config.standalone_mode:
        logging.info("Starting Reachy Mini in standalone mode (no AI agent)")
    else:
        logging.info("Starting Reachy Mini with Hermes Agent")
        logging.info(f"Model: {config.model}")
        logging.info(f"Hermes home: {config.hermes_home}")

    logging.info(f"STT: {config.stt_backend} ({config.whisper_model})")
    if config.wake_word:
        logging.info(f"Wake word: {config.wake_word}")

    # Connect to Reachy before async loop — WebRTC media backend
    # needs its own event loop which conflicts with asyncio.run()
    interface = ReachyInterface(config)
    interface.connect_reachy()

    exit_code = asyncio.run(async_main(interface))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

"""Main Reachy Mini interface for Hermes Agent."""

from __future__ import annotations

import asyncio
import logging
import os
import random
import subprocess
import sys
import tempfile
import time
from enum import Enum, auto

import numpy as np

from hermes_reachy_mini.audio import AudioCapture, WakeWordDetector
from hermes_reachy_mini.config import Config
from hermes_reachy_mini.stt import STTBackend, create_stt_backend

logger = logging.getLogger(__name__)


class InterfaceState(Enum):
    """Current state of the interface."""

    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()


class ReachyInterface:
    """
    Main interface connecting Reachy Mini to Hermes Agent.

    Handles the voice conversation loop:
    1. Capture audio from Reachy Mini's microphone
    2. Transcribe speech to text
    3. Send to Hermes Agent (embedded AIAgent)
    4. Receive response
    5. Speak response through Reachy Mini
    6. Animate robot during conversation
    """

    def __init__(self, config: Config):
        self.config = config
        self.state = InterfaceState.IDLE

        # Components
        self._reachy = None
        self._agent = None
        self._stt: STTBackend | None = None
        self._audio: AudioCapture | None = None
        self._wake_detector: WakeWordDetector | None = None

        # TTS cache
        self._tts_model = None

        # State
        self._running = False
        self._conversation_active = False

    async def start(self) -> None:
        """Start the interface. connect_reachy() must be called before this."""
        logger.info("Starting Reachy Mini interface...")

        # Initialize STT
        logger.info("Loading speech recognition model...")
        self._stt = create_stt_backend(self.config)
        await asyncio.to_thread(self._stt.preload)
        logger.info("Speech recognition ready")

        self._audio = AudioCapture(self.config, self._reachy)

        if self.config.wake_word:
            self._wake_detector = WakeWordDetector(self.config.wake_word)

        # Initialize Hermes Agent (unless standalone mode)
        if not self.config.standalone_mode:
            self._init_hermes_agent()
            # Share robot connection with plugin (must be after agent init loads plugins)
            if self._reachy:
                self._share_reachy_with_plugin()
        else:
            logger.info("Running in standalone mode - no AI agent")

        # Start audio capture
        await self._audio.start()

        self._running = True
        self.state = InterfaceState.IDLE

        # Wake up the robot
        if self._reachy:
            logger.info("Waking up Reachy...")
            await asyncio.to_thread(self._reachy.wake_up)
            await asyncio.sleep(0.5)

        logger.info("Reachy Mini interface started")
        logger.info("=" * 50)
        if self.config.wake_word:
            logger.info(f'Say "{self.config.wake_word}" to activate')
        else:
            logger.info("Speak anytime - I'm always listening!")
        logger.info("=" * 50)

        # Startup claw snap animation (radians: 0.7 ~ 40 degrees)
        if self._reachy:
            try:
                self._reachy.set_target_antenna_joint_positions([0.7, -0.7])
                await asyncio.sleep(0.2)
                self._reachy.set_target_antenna_joint_positions([-0.7, 0.7])
                await asyncio.sleep(0.2)
                self._reachy.set_target_antenna_joint_positions([0.0, 0.0])
            except Exception as e:
                logger.debug(f"Startup animation failed: {e}")

    def _init_hermes_agent(self) -> None:
        """Initialize the embedded Hermes AIAgent."""
        agent_path = self.config.hermes_agent_path
        if not agent_path.exists():
            raise FileNotFoundError(
                f"Hermes agent not found at {agent_path}. "
                "Set HERMES_HOME or --hermes-home to the correct path."
            )

        # Add hermes-agent to sys.path for imports
        agent_path_str = str(agent_path)
        if agent_path_str not in sys.path:
            sys.path.insert(0, agent_path_str)

        from run_agent import AIAgent
        from hermes_cli.config import load_config as load_hermes_config

        # Read model/provider/base_url from ~/.hermes/config.yaml
        hermes_cfg = load_hermes_config()
        model_cfg = hermes_cfg.get("model", {})
        model = model_cfg.get("default", "anthropic/claude-opus-4.6")
        provider = model_cfg.get("provider")
        base_url = model_cfg.get("base_url")

        logger.info(f"Initializing Hermes Agent (model={model}, provider={provider})...")
        kwargs = {"quiet_mode": True, "platform": "reachy-mini", "model": model}
        if provider:
            kwargs["provider"] = provider
        if base_url:
            kwargs["base_url"] = base_url

        self._agent = AIAgent(**kwargs)
        logger.info("Hermes Agent ready")

    async def stop(self) -> None:
        """Stop the interface."""
        logger.info("Stopping Reachy Mini interface...")

        self._running = False

        if self._audio:
            await self._audio.stop()

        if self._reachy:
            self._reachy.__exit__(None, None, None)
            self._reachy = None

        self.state = InterfaceState.IDLE
        logger.info("Reachy Mini interface stopped")

    async def run(self) -> None:
        """Main conversation loop."""
        if not self._running:
            await self.start()

        logger.info("Entering conversation loop...")

        idle_task = None
        if self.config.idle_animations:
            idle_task = asyncio.create_task(self._idle_animation_loop())

        try:
            while self._running:
                await self._conversation_turn()

        except asyncio.CancelledError:
            logger.info("Conversation loop cancelled")
        except Exception as e:
            logger.error(f"Error in conversation loop: {e}")
            self.state = InterfaceState.ERROR
        finally:
            if idle_task:
                idle_task.cancel()
                try:
                    await idle_task
                except asyncio.CancelledError:
                    pass

    async def _conversation_turn(self) -> None:
        """Handle one turn of conversation."""
        # Listen for speech
        self.state = InterfaceState.LISTENING
        logger.info("Listening... (speak now)")
        audio = await self._audio.capture_utterance()

        if audio is None:
            await asyncio.sleep(0.1)
            return

        # Transcribe
        self.state = InterfaceState.PROCESSING
        logger.info("Processing speech...")
        try:
            text = await asyncio.to_thread(
                self._stt.transcribe, audio, self.config.sample_rate
            )
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return

        if not text or not text.strip():
            logger.info("(no speech detected)")
            return

        logger.info(f'You said: "{text}"')

        # Check wake word if configured
        if self._wake_detector and not self._conversation_active:
            if not self._wake_detector.detect(text):
                logger.info(f'Waiting for wake word "{self.config.wake_word}"...')
                return
            logger.info("Wake word detected!")

            # Claw snap animation on activation (radians: 0.7 ~ 40 degrees)
            if self._reachy:
                try:
                    self._reachy.set_target_antenna_joint_positions([0.7, -0.7])
                    await asyncio.sleep(0.2)
                    self._reachy.set_target_antenna_joint_positions([-0.7, 0.7])
                    await asyncio.sleep(0.2)
                    self._reachy.set_target_antenna_joint_positions([0.0, 0.0])
                except Exception as e:
                    logger.error(f"Antenna animation failed: {e}")

            text = text.lower().replace(self.config.wake_word.lower(), "").strip()
            self._conversation_active = True

        if not text:
            return

        # Get response
        if self.config.standalone_mode:
            response = f"I heard you say: {text}"
        else:
            logger.info("Sending to AI...")

            # Start lobster claw animation while waiting
            animation_task = None
            if self._reachy:
                animation_task = asyncio.create_task(self._lobster_claw_animation())
                await asyncio.sleep(0.1)

            try:
                response = await asyncio.to_thread(self._agent.chat, text)
            except Exception as e:
                logger.error(f"Agent error: {e}")
                if self.config.play_emotions:
                    await self._play_emotion("sad")
                return
            finally:
                if animation_task:
                    animation_task.cancel()
                    try:
                        await animation_task
                    except asyncio.CancelledError:
                        pass
                    # Reset antennas to neutral
                    if self._reachy:
                        try:
                            self._reachy.set_target_antenna_joint_positions([0.0, 0.0])
                        except Exception:
                            pass

        logger.info(f'Response: "{response}"')

        # Speak response
        self.state = InterfaceState.SPEAKING
        logger.info("Speaking response...")
        await self._speak(response)

        # Return to idle
        self.state = InterfaceState.IDLE
        logger.info("Ready for next turn")

    def _ensure_reachy_daemon(self) -> None:
        """Check dashboard reachability and start the daemon if not running."""
        import httpx

        base_url = self.config.reachy_dashboard_url

        try:
            resp = httpx.get(f"{base_url}/api/daemon/status", timeout=3.0)
            resp.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"Reachy dashboard not reachable at {base_url}: {e}")

        state = resp.json().get("state", "unknown")
        if state == "running":
            logger.debug("Reachy daemon already running")
            return

        logger.info(f"Reachy daemon state: {state!r} — starting daemon...")
        try:
            httpx.post(f"{base_url}/api/daemon/start?wake_up=true", timeout=5.0)
        except Exception as e:
            raise ConnectionError(f"Failed to start Reachy daemon: {e}")

        for _ in range(30):
            time.sleep(2.0)
            try:
                resp = httpx.get(f"{base_url}/api/daemon/status", timeout=3.0)
                if resp.json().get("state") == "running":
                    logger.info("Reachy daemon is running")
                    return
            except Exception:
                pass

        raise TimeoutError("Reachy daemon did not reach running state within 60s")

    def connect_reachy(self) -> None:
        """Connect to Reachy Mini robot, retrying with exponential backoff."""
        try:
            from reachy_mini import ReachyMini
        except ImportError:
            logger.warning("reachy-mini not installed, running in simulation mode")
            self._reachy = None
            return

        delay = 2.0
        max_delay = 60.0
        attempt = 0

        while True:
            attempt += 1
            try:
                self._ensure_reachy_daemon()

                kwargs = {}
                if self.config.reachy_connection_mode != "auto":
                    kwargs["connection_mode"] = self.config.reachy_connection_mode
                if self.config.reachy_media_backend != "default":
                    kwargs["media_backend"] = self.config.reachy_media_backend

                self._reachy = ReachyMini(**kwargs)
                self._reachy.__enter__()
                logger.info("Connected to Reachy Mini")
                return
            except Exception as e:
                logger.warning(
                    f"Failed to connect to Reachy Mini (attempt {attempt}): {e}"
                )
                logger.info(f"Retrying in {delay:.0f}s...")
                time.sleep(delay)
                delay = min(delay * 2, max_delay)

    def _share_reachy_with_plugin(self) -> None:
        """Share the Reachy connection with the hermes plugin bridge."""
        try:
            # After _init_hermes_agent(), plugins are loaded under hermes_plugins.*
            from hermes_plugins.reachy_mini.reachy_bridge import get_bridge
            bridge = get_bridge()
            if not bridge.is_connected:
                bridge._mini = self._reachy
                bridge._connected = True
                logger.info("Shared Reachy connection with plugin bridge")
        except ImportError as e:
            logger.debug(f"Plugin bridge not available for connection sharing: {e}")

    def _load_omnivoice_model(self):
        """Load OmniVoice model (called from thread)."""
        import torch
        from omnivoice import OmniVoice

        # Use CPU if no GPU available, otherwise use auto
        device_map = "cpu"
        try:
            if torch.cuda.is_available():
                device_map = "cuda:0"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device_map = "mps"
        except Exception:
            pass

        logger.info(f"Loading OmniVoice model on {device_map}...")
        model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=device_map,
            dtype=torch.float16,
        )
        logger.info("OmniVoice model loaded successfully")
        return model

    async def _speak(self, text: str) -> None:
        """Speak text through Reachy Mini using OmniVoice TTS."""
        clean_text = text.replace("**", "").replace("*", "").replace("`", "")
        temp_wav_path: str | None = None
        resampled_path: str | None = None

        try:
            logger.info("Generating speech with OmniVoice...")

            # Load model lazily on first call
            if self._tts_model is None:
                self._tts_model = await asyncio.to_thread(self._load_omnivoice_model)

            # Generate audio synchronously using fixed reference voice
            ref_audio_path = "~/Documents/reachy-mini-hermes-agent/ref_voice.wav"

            audio_result = await asyncio.to_thread(
                self._tts_model.generate,
                text=clean_text,
                ref_audio=ref_audio_path,
                ref_text="Hello, I am Jerry. Nice to meet you. I'll be talking to you soon.",
                num_step=16,  # 16 steps for speed; 32 is default quality
                speed=1.0,
            )

            # OmniVoice returns a list of numpy arrays: [audio_np, ...]
            if not audio_result or audio_result[0].size == 0:
                logger.warning("OmniVoice produced no audio output")
                return

            audio_np = audio_result[0]

            # OmniVoice outputs at 24kHz; Reachy expects 16kHz mono 16-bit
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wf:
                temp_wav_path = wf.name

            import soundfile as sf

            sf.write(temp_wav_path, audio_np, 24000)

            # Resample to 16kHz using ffmpeg (already widely available)
            resampled_path = temp_wav_path + ".16k.wav"
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", temp_wav_path,
                    "-ar", "16000",
                    "-ac", "1",
                    resampled_path,
                ],
                capture_output=True,
                check=True,
            )

            try:
                if self._reachy and self.config.reachy_media_backend != "no_media":
                    import wave

                    with wave.open(resampled_path, "rb") as wf:
                        audio_data = np.frombuffer(
                            wf.readframes(wf.getnframes()), dtype=np.int16
                        )
                        audio_float = audio_data.astype(np.float32) / 32768.0

                    self._reachy.media.start_playing()
                    sample_rate = 16000
                    chunk_size = 1600  # 100ms chunks
                    chunk_duration = chunk_size / sample_rate

                    speak_animation_task = asyncio.create_task(
                        self._speak_animation(len(audio_float) / sample_rate)
                    )

                    total_chunks = len(audio_float) // chunk_size
                    logger.info(f"Speaking with {total_chunks} chunks...")

                    for i in range(0, len(audio_float), chunk_size):
                        chunk = audio_float[i : i + chunk_size]
                        self._reachy.media.push_audio_sample(chunk)
                        await asyncio.sleep(chunk_duration * 0.9)

                    speak_animation_task.cancel()
                    try:
                        await speak_animation_task
                    except asyncio.CancelledError:
                        pass
                    logger.info("Speech done, resetting head")
                    self._reachy.set_target_antenna_joint_positions([0.0, 0.0])
                    await asyncio.sleep(0.5)
                    self._reachy.media.stop_playing()
                else:
                    # Fallback: play locally (resampled version)
                    subprocess.run(
                        ["aplay", "-r", "16000", resampled_path], capture_output=True
                    )
            except Exception as e:
                logger.error(f"Reachy TTS playback failed: {e}")
                subprocess.run(
                    ["aplay", "-r", "16000", resampled_path], capture_output=True
                )

        except subprocess.CalledProcessError as e:
            logger.error(f"TTS processing failed: {e}")
            logger.error(e.stderr.decode("utf-8") if e.stderr else "Unknown error")
            logger.info(f"[TTS] {text}")
        except Exception as e:
            logger.error(f"OmniVoice TTS failed: {e}")
            import traceback

            traceback.print_exc()
            logger.info(f"[TTS] {text}")
        finally:
            for path in (temp_wav_path,):
                if path:
                    try:
                        os.unlink(path)
                    except FileNotFoundError:
                        pass
            if resampled_path and os.path.exists(resampled_path):
                try:
                    os.unlink(resampled_path)
                except FileNotFoundError:
                    pass

    async def _play_emotion(self, emotion: str) -> None:
        """Play emotion animation on Reachy Mini."""
        if self._reachy and hasattr(self._reachy, "play_emotion"):
            try:
                await asyncio.to_thread(self._reachy.play_emotion, emotion)
            except Exception as e:
                logger.debug(f"Emotion playback failed: {e}")

    async def _speak_animation(self, duration: float) -> None:
        """Animate head bobbing while speaking to simulate talking."""
        if not self._reachy:
            return

        from reachy_mini.utils import create_head_pose

        logger.info(f"Starting head bob animation for {duration:.1f}s")
        bob_state = 0
        try:
            while True:
                if bob_state == 0:
                    pose = create_head_pose(pitch=3, degrees=True)
                    bob_state = 1
                else:
                    pose = create_head_pose(pitch=-3, degrees=True)
                    bob_state = 0
                self._reachy.set_target_head_pose(pose)
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            try:
                self._reachy.set_target_head_pose(create_head_pose(pitch=0, degrees=True))
            except Exception:
                pass
            logger.info("Head bob animation stopped")
            raise

    async def _lobster_claw_animation(self) -> None:
        """Animate antennas like lobster claws while thinking (radians: 0.7 ~ 40 degrees)."""
        if not self._reachy:
            return

        logger.info("Starting thinking claw animation...")
        try:
            while True:
                self._reachy.set_target_antenna_joint_positions([0.7, -0.7])
                await asyncio.sleep(0.35)
                self._reachy.set_target_antenna_joint_positions([-0.7, 0.7])
                await asyncio.sleep(0.35)
        except asyncio.CancelledError:
            logger.info("Claw animation stopped")
            raise

    async def _idle_animation_loop(self) -> None:
        """Play subtle idle animations when not in conversation."""
        idle_movements = [
            {"roll": 5, "pitch": 0},
            {"roll": -5, "pitch": 0},
            {"roll": 0, "pitch": 5},
            {"roll": 0, "pitch": -5},
        ]

        while self._running:
            try:
                if self.state == InterfaceState.IDLE:
                    if self._reachy and random.random() < 0.3:
                        movement = random.choice(idle_movements)
                        from reachy_mini.utils import create_head_pose

                        await asyncio.to_thread(
                            self._reachy.goto_target,
                            head=create_head_pose(**movement, degrees=True),
                            duration=2.0,
                        )

                await asyncio.sleep(5.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Idle animation error: {e}")
                await asyncio.sleep(5.0)
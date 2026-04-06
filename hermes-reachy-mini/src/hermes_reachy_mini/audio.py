"""Audio capture and processing for Reachy Mini."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

from hermes_reachy_mini.config import Config

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """A chunk of captured audio."""

    data: np.ndarray
    sample_rate: int
    timestamp: float


class AudioCapture:
    """Captures audio from Reachy Mini's microphone."""

    def __init__(self, config: Config, reachy_mini=None):
        self.config = config
        self.reachy = reachy_mini
        self._running = False
        self._buffer: deque[np.ndarray] = deque(maxlen=1000)
        self._device_id = None
        self._use_local_mic = config.reachy_media_backend == "no_media"

        if config.audio_device:
            self._device_id = self._find_device(config.audio_device)
            self._use_local_mic = True

    def _find_device(self, device_name: str) -> int | None:
        """Find audio device by name."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if device_name.lower() in d['name'].lower() and d['max_input_channels'] > 0:
                    logger.info(f"Using audio device: {d['name']} (index {i})")
                    return i
            logger.warning(f"Audio device '{device_name}' not found, using default")
            return None
        except Exception as e:
            logger.error(f"Error finding audio device: {e}")
            return None

    async def start(self) -> None:
        """Start audio capture."""
        self._running = True
        if self._use_local_mic:
            if self._device_id is not None:
                logger.info(f"Audio: local mic (device: {self.config.audio_device}, id: {self._device_id})")
            else:
                logger.info("Audio: local mic (default device)")
                try:
                    import sounddevice as sd
                    logger.info(f"Default input device: {sd.query_devices(kind='input')['name']}")
                except Exception:
                    pass
        else:
            logger.info("Audio: Reachy Mini built-in mic")

    async def stop(self) -> None:
        """Stop audio capture."""
        self._running = False
        self._close_input_stream()
        logger.info("Audio capture stopped")

    async def capture_utterance(self) -> np.ndarray | None:
        """Capture a complete utterance (speech followed by silence)."""
        if not self._running:
            return None

        frames: list[np.ndarray] = []
        silence_frames = 0
        # Chunk size varies: 1024 for sounddevice, 320 for Reachy WebRTC
        chunk_size = 320 if not self._use_local_mic else 1024
        max_silence_frames = int(self.config.silence_duration * self.config.sample_rate / chunk_size)
        max_frames = int(self.config.max_recording_duration * self.config.sample_rate / chunk_size)
        speech_detected = False
        energy_samples = []

        try:
            use_reachy_mic = (
                not self._use_local_mic
                and self.reachy
                and hasattr(self.reachy, "media")
            )
            if use_reachy_mic:
                self.reachy.media.start_recording()
                logger.debug("Started Reachy Mini audio recording")

            while self._running and len(frames) < max_frames:
                if use_reachy_mic:
                    chunk = await asyncio.to_thread(
                        self.reachy.media.get_audio_sample
                    )
                elif self._use_local_mic:
                    chunk = await self._read_local_mic(1024)
                else:
                    raise RuntimeError(
                        "Reachy Mini mic not available — robot media backend not connected"
                    )

                if chunk is None:
                    await asyncio.sleep(0.01)
                    continue

                if not isinstance(chunk, np.ndarray):
                    chunk = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0

                # Convert stereo to mono if needed
                if chunk.ndim == 2:
                    chunk = chunk.mean(axis=1)

                energy = np.abs(chunk).mean()
                energy_samples.append(energy)

                if len(energy_samples) % 32 == 0:
                    avg_energy = np.mean(energy_samples[-32:])
                    max_energy = np.max(energy_samples[-32:])
                    logger.info(
                        f"Audio: avg={avg_energy:.4f}, max={max_energy:.4f} "
                        f"(threshold: {self.config.silence_threshold})"
                    )

                if energy > self.config.silence_threshold:
                    if not speech_detected:
                        logger.info("Speech detected!")
                    speech_detected = True
                    silence_frames = 0
                    frames.append(chunk)
                elif speech_detected:
                    silence_frames += 1
                    frames.append(chunk)

                    if silence_frames >= max_silence_frames:
                        logger.info("End of speech detected")
                        break

                await asyncio.sleep(0.001)

        except Exception as e:
            logger.error(f"Error capturing audio: {e}")
            return None
        finally:
            if use_reachy_mic:
                try:
                    self.reachy.media.stop_recording()
                except Exception:
                    pass

        if not frames or not speech_detected:
            return None

        audio = np.concatenate(frames)
        duration = len(audio) / self.config.sample_rate
        logger.info(f"Captured {duration:.2f}s of audio ({len(frames)} chunks, {len(audio)} samples)")
        return audio

    async def _read_local_mic(self, frames: int) -> np.ndarray | None:
        """Read from local microphone using sounddevice."""
        try:
            import sounddevice as sd

            if not hasattr(self, '_input_stream') or self._input_stream is None:
                self._input_stream = sd.InputStream(
                    samplerate=self.config.sample_rate,
                    channels=1,
                    dtype=np.float32,
                    device=self._device_id,
                    blocksize=frames,
                )
                self._input_stream.start()
                logger.debug(f"Started audio input stream on device {self._device_id}")

            data, overflowed = self._input_stream.read(frames)
            if overflowed:
                logger.warning("Audio buffer overflow - some audio was lost")
            return data.flatten()

        except ImportError:
            logger.warning("sounddevice not available for local mic")
            return None
        except Exception as e:
            logger.error(f"Error reading local mic: {e}")
            return None

    def _close_input_stream(self):
        """Close the input stream if open."""
        if hasattr(self, '_input_stream') and self._input_stream is not None:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception:
                pass
            self._input_stream = None


class WakeWordDetector:
    """Detects wake word in audio stream."""

    def __init__(self, wake_word: str, threshold: float = 0.8):
        self.wake_word = wake_word.lower()
        self.threshold = threshold

    def detect(self, text: str) -> bool:
        """Check if wake word is in transcribed text."""
        return self.wake_word in text.lower()

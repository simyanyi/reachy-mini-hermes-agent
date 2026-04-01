# Reachy Hermes

Voice-controlled AI embodiment for the [Pollen Robotics Reachy Mini](https://www.pollen-robotics.com/reachy-mini/) using [Hermes Agent](https://github.com/hermes-ai/hermes-agent) as the AI backend.

Talk to the robot through its built-in microphone. Hermes Agent processes your speech, generates a response, and the robot speaks back while expressing itself through head movements, antenna gestures, and emotions.

```
  Reachy Mic ──> Whisper STT ──> Hermes Agent ──> ElevenLabs TTS ──> Reachy Speaker
                                      │
                                      ├── reachy_move_head
                                      ├── reachy_play_emotion
                                      ├── reachy_move_antennas
                                      └── reachy_dance
```

## Architecture

The project has three components:

| Component | Path | Purpose |
|-----------|------|---------|
| **hermes-reachy-plugin** | `hermes-reachy-plugin/` | Hermes plugin exposing 9 robot control tools to the AI |
| **hermes-reachy-mini** | `hermes-reachy-mini/` | Voice interface: audio capture, STT, AI, TTS, playback |
| **skill** | `skills/reachy-mini/` | Behavioral instructions for the embodied AI |

### Plugin Tools

The plugin gives the AI agent direct control over the robot:

| Tool | Description |
|------|-------------|
| `reachy_connect` | Connect to the robot (usually pre-connected by the voice interface) |
| `reachy_disconnect` | Disconnect from the robot |
| `reachy_move_head` | Move head with roll, pitch, yaw (degrees) and duration |
| `reachy_move_antennas` | Move antenna/claw positions (degrees) |
| `reachy_play_emotion` | Play an emotion animation (cheerful1, sad1, surprised1, ...) |
| `reachy_dance` | Trigger a dance routine |
| `reachy_capture_image` | Capture an image from the robot's camera |
| `reachy_say` | Play a short TTS utterance through the robot |
| `reachy_status` | Check robot connection state |

Emotions and dances are played via the Reachy Dashboard REST API using Pollen's recorded-move-datasets.

## Prerequisites

- **Reachy Mini** robot on the local network (default: `192.168.0.151`)
- **Hermes Agent** installed at `~/.hermes/hermes-agent/`
- **Python 3.10+** (hermes venv uses 3.11)
- **GPU** with enough VRAM for Whisper STT (~150 MB for `base` model)
- **ElevenLabs API key** for text-to-speech

## Setup

### 1. Start the Reachy daemon

The robot daemon must be running. Start it via the dashboard REST API:

```bash
curl -X POST "http://192.168.0.151:8000/api/daemon/start?wake_up=true"
```

Or use the Reachy dashboard web UI at `http://192.168.0.151:8000`.

### 2. Install the plugin

Symlink the plugin into the hermes plugins directory:

```bash
ln -s "$(pwd)/hermes-reachy-plugin" ~/.hermes/plugins/reachy-mini
```

Add `reachy` to the toolsets list in `~/.hermes/config.yaml`:

```yaml
toolsets:
- hermes-cli
- reachy
```

### 3. Install the skill

Symlink the skill into the hermes skills directory:

```bash
ln -s "$(pwd)/skills/reachy-mini" ~/.hermes/skills/reachy-mini
```

### 4. Install the voice interface

Install into the hermes agent's virtual environment:

```bash
VIRTUAL_ENV=~/.hermes/hermes-agent/venv uv pip install -e ./hermes-reachy-mini
```

Also install the Reachy SDK and WebRTC signalling package:

```bash
VIRTUAL_ENV=~/.hermes/hermes-agent/venv uv pip install -e /path/to/reachy_mini
VIRTUAL_ENV=~/.hermes/hermes-agent/venv uv pip install gst_signalling
```

### 5. Set the ElevenLabs API key

```bash
export ELEVENLABS_API_KEY=sk_your_key_here
```

Add it to `~/.bashrc` for persistence.

### 6. Configure the AI model

The voice interface reads the model configuration from `~/.hermes/config.yaml`. For a local model served by vLLM:

```yaml
model:
  default: /path/to/your/model
  provider: custom
  base_url: http://localhost:8000/v1
```

If using Whisper on GPU alongside vLLM, ensure vLLM leaves enough VRAM. Add `--gpu-memory-utilization 0.85` to your vLLM start script.

## Usage

### Full voice interaction

```bash
~/.hermes/hermes-agent/venv/bin/hermes-reachy
```

Speak into the Reachy's microphone. The AI processes your speech and responds through the robot.

### With verbose logging

```bash
~/.hermes/hermes-agent/venv/bin/hermes-reachy -v
```

### With a wake word

```bash
~/.hermes/hermes-agent/venv/bin/hermes-reachy --wake-word "hey reachy"
```

The robot only processes speech after hearing the wake word.

### Standalone mode (no AI)

Test the audio pipeline without the AI agent. Captures speech, transcribes it, and echoes back what it heard:

```bash
~/.hermes/hermes-agent/venv/bin/hermes-reachy --standalone
```

### Demo mode

Run a quick movement demo (head nods, shakes, antenna waves) to verify the robot connection:

```bash
~/.hermes/hermes-agent/venv/bin/hermes-reachy --demo
```

### All options

```
hermes-reachy [-h] [-v] [--model MODEL] [--hermes-home HERMES_HOME]
              [--reachy-mode {auto,localhost_only,network}]
              [--stt {whisper,faster-whisper,openai}]
              [--whisper-model {tiny,base,small,medium,large}]
              [--audio-device AUDIO_DEVICE] [--wake-word WAKE_WORD]
              [--no-emotions] [--no-idle] [--standalone] [--demo]
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | | ElevenLabs TTS API key |
| `HERMES_HOME` | `~/.hermes` | Path to hermes installation |
| `HERMES_MODEL` | from config.yaml | Override AI model |
| `STT_BACKEND` | `whisper` | STT engine: `whisper`, `faster-whisper`, `openai` |
| `WHISPER_MODEL` | `base` | Whisper model size |
| `WAKE_WORD` | | Wake word to activate listening |

## Troubleshooting

### Robot daemon not running

```
Failed to connect to Reachy Mini
```

Start the daemon: `curl -X POST "http://192.168.0.151:8000/api/daemon/start?wake_up=true"`

### CUDA out of memory

```
torch.OutOfMemoryError: CUDA out of memory
```

vLLM is using too much GPU memory for Whisper to load. Add `--gpu-memory-utilization 0.85` to your vLLM start script and restart it.

### Audio energy is 0.0000

The audio device has no microphone input. If using `no_media` mode, the system falls back to the server's local sounddevice which may not have a mic. Use the default media backend to capture from Reachy's built-in mic.

### GLIBCXX version not found

```
GLIBCXX_3.4.32 not found
```

Conda's `libstdc++` conflicts with system libraries. The `hermes-reachy` entry point handles this automatically via `LD_PRELOAD`. If running Python directly, prefix with:

```bash
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 python ...
```

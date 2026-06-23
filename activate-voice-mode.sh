#!/usr/bin/env bash
# Activate OmniVoice TTS for Reachy Mini
set -euo pipefail

# Configuration
PROJECT_DIR="/home/yanyi/Documents/reachy-mini-hermes-agent"
VENV="/home/yanyi/.hermes/hermes-agent/venv"
REF_FILE="$PROJECT_DIR/ref_voice.wav"

echo "╔════════════════════════════════════════════════╗"
echo "║    Activating OmniVoice TTS for Reachy Mini   ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check venv
if [[ ! -d "$VENV" ]]; then
    echo "  ✗ Venv not found at $VENV"
    exit 1
fi

# Check omnivoice
"$VENV/bin/python" -c "from omnivoice import OmniVoice" 2>/dev/null || {
    echo "  Installing omnivoice..."
    "$VENV/bin/pip" install omnivoise
}

# Check FFmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "  Installing FFmpeg..."
    sudo apt install -y ffmpeg
fi

# Check reference voice
if [[ ! -f "$REF_FILE" ]]; then
    echo "  Generating reference voice..."
    "$VENV/bin/edge-tts" --voice en-US-AriaNeural \
        --text "Hello, I am Jerry. Nice to meet you. I'll be talking to you soon." \
        --write-media "$REF_FILE"
    echo "  ✓ Reference voice generated at $REF_FILE"
fi

# Verify code changes
echo "  Checking code patches..."
if grep -q "tts_backend" "$PROJECT_DIR/hermes-reachy-mini/src/hermes_reachy_mini/config.py"; then
    echo "  ✓ Config updated with TTS backend option"
else
    echo "  ✗ Config not patched — running main.py with --tts omnivoice will use default ElevenLabs"
fi

# Test OmniVoice
echo ""
echo "Testing OmniVoice..."
"$VENV/bin/python" -c "
import asyncio
import os
from hermes_reachy_mini.omnivoice import generate_omnivoice_audio

async def test():
    ref_audio = '$REF_FILE'
    if not os.path.exists(ref_audio):
        print(f'  ✗ Reference voice not found: {ref_audio}')
        return False
    print('  Loading OmniVoice model (first time takes ~60s)...')
    audio = await generate_omnivoice_audio(
        text='Hello, I am Jerry. Nice to meet you.',
        ref_audio=ref_audio,
        ref_text='Hello, I am Jerry. Nice to meet you. I will be talking to you soon.',
        num_step=16,
    )
    print(f'  ✓ Generated {audio.size} samples at 24kHz')
    return True

result = asyncio.run(test())
exit(0 if result else 1)
"

echo ""
echo "════════════════════════════════════════════════"
echo "  Voice Mode Activated Successfully! ✓"
echo "════════════════════════════════════════════════"
echo ""
echo "To start voice conversation:"
echo "  cd $PROJECT_DIR/hermes-reachy-mini"
echo "  source $VENV/bin/activate"
echo "  python src/hermes_reachy_mini/main.py \\"
echo "    --tts omnivoice \\"
echo "    --ref-audio $REF_FILE \\"
echo "    --stt faster-whisper \\"
echo "    --wake-word \"hey reachy\""
echo ""
echo "Press Ctrl+C to stop voice mode."
"""Shared fixtures for Forge tests."""

from __future__ import annotations

import pytest

SAMPLE_AGENTS_YAML = """\
settings:
  hotkey: "<ctrl>+<shift>+n"
  audio_device: 2
  log_level: INFO

agents:
  navi:
    type: openclaw
    wake_word: assets/hey-navi.ppn
    endpoint: http://localhost:18789
    token_env: OPENCLAW_TOKEN
    voice: google/en-US-Chirp3-HD-Erinome
    fallback_voice: en-US-AvaMultilingualNeural
  anthem:
    type: anthem
    wake_word: assets/hey-anthem.ppn
    endpoint: ws://localhost:8081
    token_env: ANTHEM_TOKEN
    voice: google/en-US-Chirp3-HD-Algieba
    fallback_voice: en-US-AndrewNeural
  dispatch:
    type: anthem
    wake_word: assets/hey-dispatch.ppn
    endpoint: ws://localhost:8082
    token_env: DISPATCH_ANTHEM_TOKEN
    voice: google/en-US-Chirp3-HD-Charon
    fallback_voice: en-US-BrianNeural
  rebel-tower:
    type: anthem
    wake_word: assets/hey-rebel-tower.ppn
    endpoint: ws://localhost:8083
    token_env: REBELTOWER_ANTHEM_TOKEN
    voice: google/en-US-Chirp3-HD-Leda
    fallback_voice: en-US-DavisNeural
  forge:
    type: anthem
    wake_word: assets/hey-forge.ppn
    endpoint: ws://localhost:8084
    token_env: FORGE_ANTHEM_TOKEN
    voice: google/en-US-Chirp3-HD-Aoede
    fallback_voice: en-US-EmmaNeural
"""


@pytest.fixture()
def agents_yaml_file(tmp_path):
    """Write sample agents.yaml to tmp_path and return the path string."""
    path = tmp_path / "agents.yaml"
    path.write_text(SAMPLE_AGENTS_YAML, encoding="utf-8")
    return str(path)

"""Forge: Project scaffolding helpers for Anthem agents."""

from __future__ import annotations

import logging
import re
import secrets
import subprocess
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DISPATCH_PATH = r"C:\Users\I9 Ultra\Dispatch"

VOICE_POOL: list[tuple[str, str]] = [
    ("google/en-US-Chirp3-HD-Puck", "en-US-GuyNeural"),
    ("google/en-US-Chirp3-HD-Kore", "en-US-JennyNeural"),
    ("google/en-US-Chirp3-HD-Fenrir", "en-US-RogerNeural"),
    ("google/en-US-Chirp3-HD-Sulafat", "en-US-MichelleNeural"),
    ("google/en-US-Chirp3-HD-Orus", "en-US-JasonNeural"),
    ("google/en-US-Chirp3-HD-Zephyr", "en-US-SaraNeural"),
    ("google/en-US-Chirp3-HD-Achernar", "en-US-TonyNeural"),
    ("google/en-US-Chirp3-HD-Gacrux", "en-US-NancyNeural"),
    ("google/en-US-Chirp3-HD-Vindemiatrix", "en-US-SteffanNeural"),
    ("google/en-US-Chirp3-HD-Sadachbia", "en-US-JennyMultilingualNeural"),
]

RESERVED_NAMES = {"con", "prn", "aux", "nul", "com1", "lpt1", "forge", "dispatch", "anthem"}


# ---------------------------------------------------------------------------
# Port allocation
# ---------------------------------------------------------------------------


def get_used_ports(agents_yaml_path: str) -> list[int]:
    """Read Dispatch's agents.yaml and extract port numbers from endpoint URLs."""
    path = Path(agents_yaml_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or "agents" not in data:
        return []
    ports: list[int] = []
    for agent in data["agents"].values():
        endpoint = agent.get("endpoint", "")
        match = re.search(r":(\d+)$", endpoint)
        if match:
            ports.append(int(match.group(1)))
    return sorted(ports)


def next_available_port(agents_yaml_path: str, start: int = 8085) -> int:
    """Return the first port >= start not already used in agents.yaml."""
    used = set(get_used_ports(agents_yaml_path))
    port = start
    while port in used:
        port += 1
    return port


# ---------------------------------------------------------------------------
# Voice allocation
# ---------------------------------------------------------------------------


def get_used_voices(agents_yaml_path: str) -> set[str]:
    """Return the set of voice field values from agents.yaml."""
    path = Path(agents_yaml_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or "agents" not in data:
        return set()
    return {agent["voice"] for agent in data["agents"].values() if "voice" in agent}


def allocate_voice(agents_yaml_path: str) -> tuple[str, str]:
    """Return the first unused (primary, fallback) voice pair from the pool."""
    used = get_used_voices(agents_yaml_path)
    for primary, fallback in VOICE_POOL:
        if primary not in used:
            return primary, fallback
    raise RuntimeError("Voice pool exhausted: all voices are already assigned")


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------


def generate_token(length: int = 32) -> str:
    """Return a cryptographically random hex string (default 64 hex chars)."""
    return secrets.token_hex(length)


# ---------------------------------------------------------------------------
# YAML / env editing
# ---------------------------------------------------------------------------


def add_agent_to_dispatch(
    agents_yaml_path: str,
    name: str,
    port: int,
    token_env: str,
    voice: str,
    fallback_voice: str,
    wake_phrase: str,
) -> None:
    """Add a new agent entry to Dispatch's agents.yaml. Idempotent."""
    path = Path(agents_yaml_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if name in data.get("agents", {}):
        logger.debug("Agent %s already exists in agents.yaml, skipping", name)
        return
    data.setdefault("agents", {})[name] = {
        "type": "anthem",
        "wake_phrase": wake_phrase,
        "endpoint": f"ws://localhost:{port}",
        "token_env": token_env,
        "voice": voice,
        "fallback_voice": fallback_voice,
    }
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def add_token_to_env(env_path: str, key: str, value: str) -> None:
    """Append KEY=value to a .env file. Skip if key already present."""
    path = Path(env_path)
    if path.exists():
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith(f"{key}="):
                logger.debug("Key %s already exists in %s, skipping", key, env_path)
                return
    else:
        content = ""
    suffix = "" if content.endswith("\n") or not content else "\n"
    path.write_text(content + suffix + f"{key}={value}\n", encoding="utf-8")


def add_token_to_channels_yaml(channels_yaml_path: str, name: str, token: str) -> None:
    """Add a name: {token: ...} entry to channels.yaml. Create if missing."""
    path = Path(channels_yaml_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}
    if name in data:
        logger.debug("Entry %s already exists in channels.yaml, skipping", name)
        return
    data[name] = {"token": token}
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_project_name(name: str) -> str:
    """Sanitize a project name: lowercase, hyphens, no special chars."""
    sanitized = name.lower().strip()
    sanitized = sanitized.replace(" ", "-")
    sanitized = re.sub(r"[^a-z0-9-]", "", sanitized)
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    if not sanitized:
        raise ValueError(f"Invalid project name: {name!r} (empty after sanitization)")
    if sanitized in RESERVED_NAMES:
        raise ValueError(f"Reserved project name: {sanitized!r}")
    return sanitized


def validate_port_free(port: int, agents_yaml_path: str) -> bool:
    """Return True if port is not already used in agents.yaml."""
    return port not in get_used_ports(agents_yaml_path)


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------

WORKFLOW_TEMPLATE = """\
channels:
  - kind: dispatch
    target: "localhost:{{{{port}}}}"
    events: [task.completed, task.failed]

agent:
  command: "claude"
  max_turns: 10
  max_concurrent: 1
  stall_timeout_ms: 300000
  max_retry_backoff_ms: 300000
  permission_mode: "dontAsk"

system:
  workflow_changes_require_approval: true

server:
  port: 0
"""

GITIGNORE_CONTENT = """\
workspaces/
.env
__pycache__/
.venv/
*.log
.claude/
.cursor/
.pytest_cache/
"""


def scaffold_project(
    base_path: str,
    name: str,
    repo_url: str | None,
    tech_stack: str,
) -> dict:
    """Full scaffolding pipeline. Returns a summary dict."""
    sanitized = validate_project_name(name)
    project_dir = Path(base_path) / sanitized
    project_dir.mkdir(parents=True, exist_ok=True)

    agents_yaml_path = str(Path(DISPATCH_PATH) / "agents.yaml")
    env_path = str(Path(DISPATCH_PATH) / ".env")
    channels_yaml_path = str(Path.home() / ".anthem" / "channels.yaml")

    if repo_url:
        subprocess.run(["git", "clone", repo_url, "."], cwd=project_dir, check=True)
    else:
        subprocess.run(["git", "init"], cwd=project_dir, check=True)

    subprocess.run(["anthem", "init"], cwd=project_dir, check=True)

    port = next_available_port(agents_yaml_path)
    primary_voice, fallback_voice = allocate_voice(agents_yaml_path)
    token = generate_token()
    wake_phrase = f"hey {sanitized}"
    token_env = f"{sanitized.upper().replace('-', '_')}_ANTHEM_TOKEN"

    workflow_content = WORKFLOW_TEMPLATE.replace("{{port}}", str(port))
    (project_dir / "WORKFLOW.md").write_text(workflow_content, encoding="utf-8")
    (project_dir / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")

    add_agent_to_dispatch(
        agents_yaml_path=agents_yaml_path,
        name=sanitized,
        port=port,
        token_env=token_env,
        voice=primary_voice,
        fallback_voice=fallback_voice,
        wake_phrase=wake_phrase,
    )
    add_token_to_env(env_path, token_env, token)
    add_token_to_channels_yaml(channels_yaml_path, sanitized, token)

    logger.info("Scaffolded project %s at %s", sanitized, project_dir)

    return {
        "path": str(project_dir),
        "port": port,
        "voice": primary_voice,
        "fallback_voice": fallback_voice,
        "wake_phrase": wake_phrase,
        "token_env": token_env,
    }

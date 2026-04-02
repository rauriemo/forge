"""Forge: Project scaffolding helpers for Anthem agents."""

from __future__ import annotations

import argparse
import json
import logging
import re
import secrets
import subprocess
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DISPATCH_PATH = r"C:\Users\I9 Ultra\Dispatch"
PRISM_PATH = r"C:\Users\I9 Ultra\prism"
SETTINGS_PATH = Path(__file__).parent / "settings.json"
GITHUB_ORG = "rauriemo"

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


def get_used_prism_ports(prism_agents_yaml_path: str) -> list[int]:
    """Read Prism's agents.yaml and extract port numbers from endpoint URLs."""
    path = Path(prism_agents_yaml_path)
    if not path.exists():
        return []
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


def next_available_prism_port(agents_yaml_path: str, prism_agents_yaml_path: str) -> int:
    """Return the first prism port >= 3101 not used in either agents.yaml."""
    used = set(get_used_ports(agents_yaml_path)) | set(get_used_prism_ports(prism_agents_yaml_path))
    port = 3101
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
) -> None:
    """Add a new agent entry to Dispatch's agents.yaml. Idempotent.

    New agents use STT-based wake phrase detection (derived from the agent name)
    rather than Picovoice .ppn files. Dispatch falls back to the STT pipeline
    when the .ppn file doesn't exist, deriving the phrase from the filename.
    """
    path = Path(agents_yaml_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if name in data.get("agents", {}):
        logger.debug("Agent %s already exists in agents.yaml, skipping", name)
        return
    data.setdefault("agents", {})[name] = {
        "type": "anthem",
        "wake_word": f"assets/hey-{name}.ppn",
        "endpoint": f"ws://localhost:{port}",
        "token_env": token_env,
        "voice": voice,
        "fallback_voice": fallback_voice,
    }
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def add_agent_to_prism(
    prism_agents_yaml_path: str,
    name: str,
    prism_port: int,
    voice: str,
    fallback_voice: str,
) -> None:
    """Add a new agent entry to Prism's agents.yaml. Idempotent."""
    path = Path(prism_agents_yaml_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}
    if name in data.get("agents", {}):
        logger.debug("Agent %s already exists in Prism agents.yaml, skipping", name)
        return
    data.setdefault("agents", {})[name] = {
        "type": "anthem",
        "endpoint": f"ws://localhost:{prism_port}",
        "token_env": "PRISM_ANTHEM_TOKEN",
        "voice": voice,
        "fallback_voice": fallback_voice,
    }
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    logger.info("Registered agent %s in Prism agents.yaml on port %d", name, prism_port)


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


def get_dispatch_token(channels_yaml_path: str) -> str:
    """Read the shared dispatch token from channels.yaml.

    All Anthem instances share a single ``dispatch.token`` entry. Anthem's
    ``ChannelsConfig`` struct only has ``dispatch`` and ``slack`` fields, so
    per-project keys are ignored.
    """
    path = Path(channels_yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"channels.yaml not found at {channels_yaml_path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    dispatch = data.get("dispatch", {})
    token = dispatch.get("token", "")
    if not token:
        raise ValueError("No dispatch.token found in channels.yaml")
    return token


def get_prism_token(channels_yaml_path: str) -> str:
    """Read the shared prism token from channels.yaml.

    If prism.token doesn't exist yet, generate one and write it back.
    """
    path = Path(channels_yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"channels.yaml not found at {channels_yaml_path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    prism = data.get("prism", {})
    token = prism.get("token", "")
    if not token:
        token = generate_token()
        data.setdefault("prism", {})["token"] = token
        path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Generated prism token in %s", channels_yaml_path)
    return token


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def load_settings() -> dict:
    """Load forge settings from settings.json. Returns defaults if missing."""
    if SETTINGS_PATH.exists():
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    return {"repo_visibility": "public"}


def save_settings(settings: dict) -> None:
    """Persist forge settings to settings.json."""
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def set_repo_visibility(visibility: str) -> dict:
    """Toggle default repo visibility. Returns updated settings."""
    if visibility not in ("public", "private"):
        raise ValueError(f"Invalid visibility: {visibility!r} (must be 'public' or 'private')")
    settings = load_settings()
    settings["repo_visibility"] = visibility
    save_settings(settings)
    logger.info("Repo visibility set to %s", visibility)
    return settings


# ---------------------------------------------------------------------------
# GitHub repo creation
# ---------------------------------------------------------------------------


def create_github_repo(project_dir: str, name: str, private: bool = False) -> str:
    """Create a GitHub repo under GITHUB_ORG, commit local files, and push.

    Uses ``gh repo create`` which sets the remote and pushes in one step.
    Returns the repo URL.
    """
    visibility = "--private" if private else "--public"
    cwd = str(project_dir)

    subprocess.run(["git", "add", "."], cwd=cwd, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Initial scaffold for {name}"],
        cwd=cwd,
        check=True,
    )
    subprocess.run(
        ["gh", "repo", "create", f"{GITHUB_ORG}/{name}", visibility, "--source=.", "--push"],
        cwd=cwd,
        check=True,
    )
    return f"https://github.com/{GITHUB_ORG}/{name}"


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
---
tracker:
  kind: github
  repo: "{repo}"
  labels:
    active: ["todo", "in-progress"]
    terminal: ["done", "canceled"]

polling:
  interval_ms: 10000

workspace:
  root: "./workspaces"

hooks: {{}}

channels:
  - kind: dispatch
    target: "localhost:{port}"
    events: [task.completed, task.failed]
  - kind: prism
    target: "localhost:{prism_port}"
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
---

You are an expert software engineer working on {{{{.issue.title}}}}.

## Task
{{{{.issue.body}}}}

## Rules
- Make small, focused commits
- Run tests before marking a task as done
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
settings.json
"""


def scaffold_project(
    base_path: str,
    name: str,
    repo_url: str | None = None,
    tech_stack: str = "general",
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
    prism_agents_yaml_path = str(Path(PRISM_PATH) / "backend" / "agents.yaml")
    prism_port = next_available_prism_port(agents_yaml_path, prism_agents_yaml_path)
    primary_voice, fallback_voice = allocate_voice(agents_yaml_path)
    token_env = f"{sanitized.upper().replace('-', '_')}_ANTHEM_TOKEN"

    shared_token = get_dispatch_token(channels_yaml_path)
    get_prism_token(channels_yaml_path)

    repo_full = f"{GITHUB_ORG}/{sanitized}"
    workflow_content = WORKFLOW_TEMPLATE.format(
        port=port, prism_port=prism_port, repo=repo_full,
    )
    (project_dir / "WORKFLOW.md").write_text(workflow_content, encoding="utf-8")
    (project_dir / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")

    add_agent_to_dispatch(
        agents_yaml_path=agents_yaml_path,
        name=sanitized,
        port=port,
        token_env=token_env,
        voice=primary_voice,
        fallback_voice=fallback_voice,
    )
    add_agent_to_prism(
        prism_agents_yaml_path=prism_agents_yaml_path,
        name=sanitized,
        prism_port=prism_port,
        voice=primary_voice,
        fallback_voice=fallback_voice,
    )
    add_token_to_env(env_path, token_env, shared_token)

    settings = load_settings()
    private = settings.get("repo_visibility", "public") == "private"
    repo_url_created = create_github_repo(str(project_dir), sanitized, private=private)

    wake_phrase = f"hey {sanitized}"
    logger.info("Scaffolded project %s at %s", sanitized, project_dir)

    return {
        "path": str(project_dir),
        "port": port,
        "prism_port": prism_port,
        "voice": primary_voice,
        "fallback_voice": fallback_voice,
        "wake_phrase": wake_phrase,
        "token_env": token_env,
        "repo": repo_url_created,
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Forge project scaffolding tool")
    sub = parser.add_subparsers(dest="command")

    scaffold_cmd = sub.add_parser("scaffold", help="Scaffold a new Anthem project")
    scaffold_cmd.add_argument("--name", required=True, help="Project name")
    scaffold_cmd.add_argument(
        "--base-path",
        required=True,
        help="Parent directory for the project",
    )
    scaffold_cmd.add_argument(
        "--repo-url",
        default=None,
        help="Git repo URL to clone",
    )
    scaffold_cmd.add_argument(
        "--tech-stack",
        default="general",
        help="Tech stack hint",
    )

    vis_cmd = sub.add_parser(
        "set-visibility",
        help="Set default repo visibility (public/private)",
    )
    vis_cmd.add_argument(
        "--value",
        required=True,
        choices=["public", "private"],
        help="Repo visibility for future scaffolds",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.command == "scaffold":
        result = scaffold_project(
            base_path=args.base_path,
            name=args.name,
            repo_url=args.repo_url,
            tech_stack=args.tech_stack,
        )
        print(json.dumps(result, indent=2))

    elif args.command == "set-visibility":
        result = set_repo_visibility(args.value)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

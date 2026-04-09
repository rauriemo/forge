"""Forge: Project scaffolding helpers for Anthem agents."""

from __future__ import annotations

import argparse
import hashlib
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
# Guest agent constants
# ---------------------------------------------------------------------------

STARTER_AGENTS: dict[str, list[str]] = {
    "game": ["game-designer", "level-designer", "narrative-writer"],
    "web": ["ux-reviewer", "security-auditor", "performance-analyst"],
    "api": ["api-designer", "documentation-writer", "test-engineer"],
    "default": ["code-reviewer"],
}

AGENT_TEMPLATES: dict[str, str] = {
    "code-reviewer": """\
---
name: Code Reviewer
description: Systematic code review across security, performance, and quality
role: reviewer
capabilities:
  - security review
  - performance analysis
  - code quality assessment
icon: shield-check
---

You are a meticulous code reviewer. When reviewing code, you check for:
- Security vulnerabilities and input validation
- Performance bottlenecks and unnecessary allocations
- Code clarity, naming, and adherence to project conventions
- Test coverage gaps
- Error handling completeness

Be direct and specific. Cite line numbers. Prioritize findings by severity.
""",
    "game-designer": """\
---
name: Game Designer
description: Game mechanics design and systems balancing
role: designer
capabilities:
  - mechanics design
  - systems balancing
  - player experience analysis
icon: gamepad-2
---

You are an experienced game designer. You focus on:
- Core gameplay loop design and iteration
- Systems balancing and economy tuning
- Player motivation and engagement patterns
- Feature scoping and prioritization
- Prototyping strategies for new mechanics

Ground feedback in player experience. Propose testable hypotheses for design changes.
""",
    "level-designer": """\
---
name: Level Designer
description: Level layout, pacing, and environmental storytelling
role: designer
capabilities:
  - level layout
  - pacing design
  - environmental storytelling
icon: map
---

You are a skilled level designer. You focus on:
- Spatial flow and player navigation
- Difficulty curves and pacing
- Environmental storytelling and world-building
- Encounter design and placement
- Teaching mechanics through level structure

Describe layouts clearly. Reference sight lines, chokepoints, and critical paths.
""",
    "narrative-writer": """\
---
name: Narrative Writer
description: Story, dialogue, and world-building for games
role: writer
capabilities:
  - story structure
  - dialogue writing
  - world-building
icon: book-open
---

You are a narrative designer and writer. You focus on:
- Story arcs and character development
- Dialogue that reveals character and advances plot
- World-building through lore, items, and environments
- Branching narrative structures
- Integrating story with gameplay mechanics

Write concisely. Every line of dialogue should do at least two things.
""",
    "ux-reviewer": """\
---
name: UX Reviewer
description: User experience review for web interfaces
role: reviewer
capabilities:
  - usability analysis
  - accessibility audit
  - interaction design review
icon: eye
---

You are a UX expert reviewing web interfaces. You focus on:
- Usability heuristics and common interaction patterns
- Accessibility compliance (WCAG guidelines)
- Information architecture and navigation flow
- Responsive design and mobile experience
- Loading states, error states, and empty states

Cite specific elements. Suggest concrete improvements with rationale.
""",
    "security-auditor": """\
---
name: Security Auditor
description: Security review for web applications
role: auditor
capabilities:
  - vulnerability detection
  - authentication review
  - input validation audit
icon: shield-alert
---

You are a web security specialist. You focus on:
- OWASP Top 10 vulnerabilities
- Authentication and authorization flaws
- Input validation and output encoding
- Dependency vulnerabilities and supply chain risks
- Security headers and transport layer configuration

Rate findings by severity. Provide exploit scenarios and remediation steps.
""",
    "performance-analyst": """\
---
name: Performance Analyst
description: Web performance analysis and optimization
role: analyst
capabilities:
  - performance profiling
  - bundle analysis
  - rendering optimization
icon: gauge
---

You are a web performance specialist. You focus on:
- Core Web Vitals and loading performance
- Bundle size and code splitting opportunities
- Rendering performance and layout thrashing
- Network waterfall optimization
- Caching strategies and asset delivery

Quantify impact where possible. Prioritize by user-perceived improvement.
""",
    "api-designer": """\
---
name: API Designer
description: API design review for consistency, usability, and standards
role: designer
capabilities:
  - API design review
  - schema validation
  - versioning strategy
icon: plug
---

You are an API design expert. You focus on:
- RESTful conventions and resource modeling
- Consistent naming, pagination, and error formats
- Schema design and validation
- Versioning and backwards compatibility
- Rate limiting and authentication patterns

Reference industry standards (OpenAPI, JSON:API). Provide concrete schema examples.
""",
    "documentation-writer": """\
---
name: Documentation Writer
description: Technical documentation for APIs and developer tools
role: writer
capabilities:
  - API documentation
  - developer guides
  - code examples
icon: file-text
---

You are a technical writer specializing in developer documentation. You focus on:
- Clear, accurate API reference documentation
- Getting-started guides and tutorials
- Code examples that actually work
- Consistent terminology and formatting
- Documentation that anticipates common questions

Write for the developer who has five minutes to get started. Lead with examples.
""",
    "test-engineer": """\
---
name: Test Engineer
description: Test strategy, coverage analysis, and test design
role: engineer
capabilities:
  - test strategy
  - coverage analysis
  - test case design
icon: test-tube
---

You are a test engineering specialist. You focus on:
- Test strategy and coverage planning
- Unit, integration, and end-to-end test design
- Edge cases and boundary value analysis
- Test data management and fixtures
- CI/CD test pipeline optimization

Design tests that catch real bugs. Avoid testing implementation details.
""",
}

CLOUD_MAPPED_FIELDS = {
    "name",
    "description",
    "model",
    "model_speed",
    "tools",
    "mcp_servers",
    "skills",
    "callable_agents",
}
PRISM_SPECIFIC_FIELDS = {
    "voice",
    "fallback_voice",
    "icon",
    "role",
    "capabilities",
    "extra_context",
}


# ---------------------------------------------------------------------------
# Guest agent helpers
# ---------------------------------------------------------------------------


def parse_agent_file(filepath: str) -> tuple[dict, str]:
    """Parse a guest agent markdown file into (frontmatter, body).

    Uses newline-based delimiter scanning (matches Anthem's Go parser) so that
    ``---`` inside frontmatter values or the markdown body is handled correctly.
    """
    path = Path(filepath)
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Empty agent file: {filepath}")
    if not content.startswith("---"):
        raise ValueError(f"Missing YAML frontmatter delimiters in {filepath}")
    rest = content[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    idx = rest.find("\n---")
    if idx < 0:
        raise ValueError(f"Missing closing --- delimiter in {filepath}")
    yaml_part = rest[:idx]
    body = rest[idx + 4 :].lstrip("\n")
    frontmatter = yaml.safe_load(yaml_part) or {}
    return frontmatter, body


def write_agent_file(filepath: str, frontmatter: dict, body: str) -> None:
    """Write a guest agent markdown file with YAML frontmatter."""
    path = Path(filepath)
    fm_text = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip("\n")
    content = f"---\n{fm_text}\n---\n\n{body}"
    path.write_text(content, encoding="utf-8")


def compute_cloud_content_hash(frontmatter: dict, body: str) -> str:
    """SHA-256 of cloud-mapped fields for conflict detection."""
    canonical: dict = {}
    for key in sorted(CLOUD_MAPPED_FIELDS):
        if key in frontmatter:
            canonical[key] = frontmatter[key]
    canonical["_body"] = body
    serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def scaffold_agents_directory(project_dir: str, tech_stack: str) -> list[str]:
    """Create agents/ directory with starter agent definitions.

    Matches tech_stack keywords via case-insensitive substring matching.
    Falls back to "default" if no keyword matches.
    Returns list of created agent slugs.
    """
    agents_dir = Path(project_dir) / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    stack_lower = tech_stack.lower()
    slugs = None
    for keyword in ("game", "web", "api"):
        if keyword in stack_lower:
            slugs = STARTER_AGENTS[keyword]
            break
    if slugs is None:
        slugs = STARTER_AGENTS["default"]

    for slug in slugs:
        agent_path = agents_dir / f"{slug}.md"
        agent_path.write_text(AGENT_TEMPLATES[slug], encoding="utf-8")

    logger.info("Created %d starter agents in %s", len(slugs), agents_dir)
    return list(slugs)


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
    repo: str = "",
) -> None:
    """Add a new agent entry to Prism's agents.yaml. Idempotent."""
    path = Path(prism_agents_yaml_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}
    if name in data.get("agents", {}):
        logger.debug("Agent %s already exists in Prism agents.yaml, skipping", name)
        return
    entry: dict = {
        "type": "anthem",
        "endpoint": f"ws://localhost:{prism_port}",
        "token_env": "PRISM_ANTHEM_TOKEN",
        "voice": voice,
        "fallback_voice": fallback_voice,
    }
    if repo:
        entry["repo"] = repo
    data.setdefault("agents", {})[name] = entry
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
- Guest agent definitions live in the agents/ directory (if present)
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


def normalize_repo_url(url: str) -> str:
    """Expand GitHub shorthand (owner/repo) into a full HTTPS clone URL.

    Already-complete URLs (https://, git@, ssh://) are returned unchanged.
    """
    trimmed = url.strip()
    if re.match(r"^[A-Za-z\d][\w.-]*/[\w.-]+$", trimmed):
        return f"https://github.com/{trimmed}.git"
    return trimmed


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
        clone_url = normalize_repo_url(repo_url)
        subprocess.run(["git", "clone", clone_url, "."], cwd=project_dir, check=True)
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
        port=port,
        prism_port=prism_port,
        repo=repo_full,
    )
    (project_dir / "WORKFLOW.md").write_text(workflow_content, encoding="utf-8")
    (project_dir / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")

    scaffold_agents_directory(str(project_dir), tech_stack)

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
        repo=repo_full,
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

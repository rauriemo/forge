# Forge -- Claude Code Context

## What Is Forge

Forge is a channel-agnostic project scaffolding agent. It is a standalone Anthem instance (https://github.com/rauriemo/anthem) that creates new projects on demand: creates the directory, runs `git init`, runs `anthem init`, writes a tailored `WORKFLOW.md`, registers the new agent in Dispatch's `agents.yaml`, assigns a unique voice, generates auth tokens, and reports back with instructions.

Forge is the orchestrator that builds other orchestrators.

Any channel can invoke Forge -- Dispatch voice ("hey forge"), Slack ("@forge"), GitHub Issues (label: todo). It sits alongside the other agents (Navi, Anthem, Dispatch, RebelTower) in the same tier, not embedded in Dispatch.

## Plans and Architecture Docs

Read this document thoroughly before writing any code:

- `docs/plan.md` -- Full implementation plan with architecture diagrams, API specs, testing strategy, phase breakdown, error corrections, and file inventory

This is the source of truth for what to build and how.

## Ecosystem Context

Forge operates within a system of three products:

- **Dispatch** (https://github.com/rauriemo/dispatch) -- Voice-first command channel for AI agents. Wake words route to agent backends. Dispatch is the voice frontend that talks to Forge via the `AnthemAgent` WebSocket protocol.
- **Anthem** (https://github.com/rauriemo/anthem) -- Hybrid orchestrator for Claude Code. Go daemon for reliability, AI orchestrator for intelligence. Forge itself IS an Anthem instance. New projects Forge creates also become Anthem instances.
- **Forge** (this project) -- Scaffolding agent. Contains `forge.py` helper library that Anthem executor agents call to do the mechanical work.

## Design Decisions (Locked In)

- **Language**: Python 3.11+
- **Single file**: All helper logic lives in `forge.py` at the project root. No package structure needed -- Anthem executor agents call it directly via `Bash(python "C:/Users/I9 Ultra/Forge/forge.py" ...)`.
- **No runtime server**: Forge has no long-running process of its own. The Anthem daemon IS the server. `forge.py` is a library/CLI that the executor agent invokes.
- **Dispatch path**: `C:\Users\I9 Ultra\Dispatch\` -- Forge reads and writes `agents.yaml`, `.env`, and `.env.example` here.
- **Channels config path**: `~/.anthem/channels.yaml` -- Forge adds token entries here for new projects.
- **Port allocation start**: 8085 (Forge itself is on 8084; existing agents use 8081-8083).
- **Voice provider**: Google Chirp3-HD primary, Edge TTS fallback. Provider prefix format matches Dispatch conventions.
- **Wake words**: STT wake phrase matching only (no `.ppn` files). Wake phrase derived from project name: "hey rpg", "hey my-app".
- **Concurrency**: `max_concurrent: 1` in WORKFLOW.md. Scaffolding is sequential to prevent port/voice race conditions.
- **Testing**: pytest with `tmp_path` for file I/O isolation. `monkeypatch` for subprocess mocking. Ruff for linting.

## Key Files

| File | Purpose |
|---|---|
| `forge.py` | All scaffolding logic: port allocation, voice allocation, token generation, YAML editing, env editing, project scaffold, validation |
| `tests/test_forge.py` | Unit tests for every public function in forge.py |
| `tests/conftest.py` | Shared fixtures (sample agents.yaml content, temp directories) |
| `WORKFLOW.md` | Anthem config for Forge itself: tracker, hooks, allowed_tools, constraints, prompt template |
| `CLAUDE.md` | This file. Architecture doc for Claude Code context. |
| `docs/plan.md` | Full implementation plan (source of truth for what to build) |
| `pyproject.toml` | pytest + ruff configuration |
| `requirements.txt` | Runtime dependency: pyyaml |
| `requirements-dev.txt` | Dev dependencies: pytest, ruff |
| `.github/workflows/ci.yml` | CI: cross-platform pytest + ruff |

## `forge.py` API Specification

### Port Allocation

```python
def get_used_ports(agents_yaml_path: str) -> list[int]
```
Reads Dispatch's `agents.yaml` and extracts the port number from every agent's `endpoint` URL. Returns a sorted list of integers.

```python
def next_available_port(agents_yaml_path: str, start: int = 8085) -> int
```
Scans from `start` upward, returns the first port not in `get_used_ports()`. The start default is 8085 because 8081-8084 are already assigned.

### Voice Allocation

```python
VOICE_POOL: list[tuple[str, str]]
```
List of `(primary_voice, fallback_voice)` tuples. Excludes voices already assigned to existing agents:
- Erinome (Navi), Algieba (Anthem), Charon (Dispatch), Leda (RebelTower), Aoede (Forge)

```python
def get_used_voices(agents_yaml_path: str) -> set[str]
```
Reads `agents.yaml`, returns the set of `voice` field values across all agents.

```python
def allocate_voice(agents_yaml_path: str) -> tuple[str, str]
```
Returns the first `(primary, fallback)` from `VOICE_POOL` whose primary is not in `get_used_voices()`. Raises `RuntimeError` if pool is exhausted.

### Token Generation

```python
def generate_token(length: int = 32) -> str
```
Returns `secrets.token_hex(length)` -- a cryptographically random hex string. Default 32 bytes = 64 hex characters.

### YAML/Env Editing

```python
def add_agent_to_dispatch(
    agents_yaml_path: str,
    name: str,
    port: int,
    token_env: str,
    voice: str,
    fallback_voice: str,
    wake_phrase: str,
) -> None
```
Reads `agents.yaml`, adds a new agent entry under `agents:` with `type: anthem`, `wake_phrase`, `endpoint: ws://localhost:{port}`, `token_env`, `voice`, `fallback_voice`. Writes back. Idempotent: if agent `name` already exists, does nothing.

```python
def add_token_to_env(env_path: str, key: str, value: str) -> None
```
Appends `KEY=value` to the `.env` file. Creates the file if missing. Skips if key already exists.

```python
def add_token_to_channels_yaml(channels_yaml_path: str, name: str, token: str) -> None
```
Reads `channels.yaml`, adds `name: { token: "..." }` entry. Preserves existing entries. Creates file with just the new entry if missing.

### Scaffold

```python
def scaffold_project(
    base_path: str,
    name: str,
    repo_url: str | None,
    tech_stack: str,
) -> dict
```
Full scaffolding pipeline:
1. Validates project name via `validate_project_name()`
2. Creates directory at `base_path/sanitized_name`
3. Runs `git init` (or `git clone repo_url .` if provided)
4. Runs `anthem init`
5. Reads Dispatch's `agents.yaml` to allocate port and voice
6. Generates a token
7. Writes WORKFLOW.md with project-specific config
8. Writes .gitignore
9. Adds agent to Dispatch's `agents.yaml`
10. Adds token to Dispatch's `.env`
11. Adds token to `~/.anthem/channels.yaml`

Returns a dict:
```python
{
    "path": "C:\\Users\\I9 Ultra\\RPG",
    "port": 8085,
    "voice": "google/en-US-Chirp3-HD-Puck",
    "fallback_voice": "en-US-GuyNeural",
    "wake_phrase": "hey rpg",
    "token_env": "RPG_ANTHEM_TOKEN",
}
```

### Validation

```python
def validate_project_name(name: str) -> str
```
Sanitizes a project name: lowercases, replaces spaces with hyphens, strips non-alphanumeric characters (except hyphens), rejects empty strings and reserved names. Returns the sanitized name.

```python
def validate_port_free(port: int, agents_yaml_path: str) -> bool
```
Returns `True` if port is not in `get_used_ports()`.

## Port Allocation Strategy

Current port assignments (read from Dispatch's `agents.yaml`):

| Port | Agent | Project |
|---|---|---|
| 8081 | Anthem | anthem repo |
| 8082 | Dispatch | dispatch repo |
| 8083 | RebelTower | rebel-tower project |
| 8084 | Forge | this project |

New projects get ports starting at 8085. `next_available_port()` scans upward from 8085 and skips any port already in use.

Port is extracted from the `endpoint` URL in `agents.yaml` (e.g., `ws://localhost:8081` -> `8081`).

## Voice Allocation Strategy

Each agent gets a unique Google Chirp3-HD voice (primary) paired with an Edge TTS fallback. The pool in `forge.py` excludes voices already assigned:

| Voice | Assigned To |
|---|---|
| `google/en-US-Chirp3-HD-Erinome` | Navi |
| `google/en-US-Chirp3-HD-Algieba` | Anthem |
| `google/en-US-Chirp3-HD-Charon` | Dispatch |
| `google/en-US-Chirp3-HD-Leda` | RebelTower |
| `google/en-US-Chirp3-HD-Aoede` | Forge |

`allocate_voice()` returns the first pool entry whose primary voice is not in `get_used_voices()`.

## File Paths Forge Manages

These are EXTERNAL files that Forge reads and writes. They do not live in this project:

| Path | What Forge Does |
|---|---|
| `C:\Users\I9 Ultra\Dispatch\agents.yaml` | Reads to find used ports/voices. Writes to register new agents. |
| `C:\Users\I9 Ultra\Dispatch\.env` | Appends new token entries (e.g., `RPG_ANTHEM_TOKEN=abc123`) |
| `C:\Users\I9 Ultra\Dispatch\.env.example` | Appends empty placeholders (e.g., `RPG_ANTHEM_TOKEN=`) |
| `~/.anthem/channels.yaml` | Adds token entries for new projects' Dispatch channel auth |

The Dispatch path should be configurable (default `C:\Users\I9 Ultra\Dispatch`), but for now it's a constant in `forge.py`. Do NOT hardcode it in multiple places.

## Testing Requirements

- **Framework**: pytest
- **Linting**: ruff (configured in `pyproject.toml`)
- **Isolation**: All file I/O uses `tmp_path` (pytest built-in). No real filesystem side effects.
- **Mocking**: `monkeypatch` on `subprocess.run` for git/anthem commands.
- **Coverage target**: Every public function in `forge.py` must have tests.
- **CI**: GitHub Actions, cross-platform (Windows + Linux).
- **Run tests**: `python -m pytest tests/ -v`
- **Run linter**: `ruff check . && ruff format --check .`

Test classes (one per concern):

| Class | Covers |
|---|---|
| `TestPortAllocation` | `get_used_ports`, `next_available_port` |
| `TestVoiceAllocation` | `get_used_voices`, `allocate_voice` |
| `TestTokenGeneration` | `generate_token` |
| `TestYamlEditing` | `add_agent_to_dispatch` |
| `TestEnvEditing` | `add_token_to_env` |
| `TestChannelsYaml` | `add_token_to_channels_yaml` |
| `TestScaffold` | `scaffold_project` |
| `TestValidation` | `validate_project_name`, `validate_port_free` |

## Coding Standards

- No unnecessary comments. Don't narrate what code does. Only comment non-obvious intent, trade-offs, or constraints.
- Type hints on all public function signatures.
- Use `pathlib.Path` internally but accept `str` in public APIs (for CLI compatibility).
- Wrap errors with context: raise descriptive messages, never swallow errors silently.
- Use `logging` for debug output, never `print()`.
- Keep `forge.py` as a single file. No package structure.

## What Forge Does NOT Do (for now)

- **Does not run `anthem run`** on the new project. The user starts it manually.
- **Does not create GitHub repos**. It runs `git init` locally. `gh repo create` can be added later.
- **Does not manage Picovoice wake words**. New projects use STT wake phrase matching only.
- **Does not have its own server**. The Anthem daemon IS the runtime. `forge.py` is invoked by executor agents.

## Anthem WORKFLOW.md Contract

Forge's own `WORKFLOW.md` follows Anthem's format: YAML front matter + Go template body separated by `---`. The executor agent runs in `./workspaces/GH-N/` (not the project root), so `allowed_tools` must reference `forge.py` by absolute path: `Bash(python "C:/Users/I9 Ultra/Forge/forge.py" *)`.

Key WORKFLOW.md settings:
- `tracker.repo: rauriemo/forge` (GitHub issue tracker)
- `channels.target: localhost:8084` (Dispatch channel adapter -- Anthem listens, Dispatch connects in)
- `server.port: 0` (dashboard disabled)
- `agent.max_concurrent: 1` (sequential scaffolding)

## Anthem API Contract (how Dispatch talks to Forge)

Forge uses the same WebSocket protocol as all Anthem agents. Dispatch's `AnthemAgent` connects via:

```
Auth:     {"type":"auth","token":"<FORGE_ANTHEM_TOKEN>","client":"dispatch"}
Response: {"type":"auth_ok"}
Request:  {"type":"req","id":"<uuid>","text":"create a new project called RPG"}
Response: {"type":"res","id":"<uuid>","text":"RPG project created at ..."}
Events:   {"type":"event","event":"task.completed","text":"..."}
```

The token lives in two places:
- Client-side: Dispatch's `.env` as `FORGE_ANTHEM_TOKEN` (AnthemAgent reads it)
- Server-side: `~/.anthem/channels.yaml` under `forge.token` (Anthem's Dispatch adapter verifies it)

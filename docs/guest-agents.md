# Guest Agents -- Forge Implementation Spec

## Overview

Forge gains new CLI subcommands for managing guest agents: installing from the cloud registry, updating, publishing, creating locally, and scaffolding starter agents when creating new projects. These commands operate on the project's `agents/` directory and `.managed-sync.json` file.

This spec covers all Forge-side changes across all phases.

## Shared Contract

### Agent file format

Markdown files with YAML frontmatter in `{project-root}/agents/`. Full format documented in the Anthem spec. Key points for Forge:

- Only `name` and `description` are required
- YAML frontmatter between `---` delimiters, markdown body below
- Prism-specific fields (`voice`, `icon`, `role`, `capabilities`, `extra_context`) are NOT synced to cloud
- Cloud-mapped fields: `name`, `description`, `model`, `model_speed`, `tools`, `mcp_servers`, `skills`, `callable_agents`, markdown body

### `.managed-sync.json` schema

```json
{
  "<slug>": {
    "managed_agent_id": "agent_01HqR2k7...",
    "managed_agent_version": 3,
    "installed_at": "2026-04-07T14:30:00Z",
    "cloud_content_hash": "sha256:7f3a1b..."
  },
  "_environments": {
    "sha256:abc123...": "env_011CZkZ9X2dpNyB7HsEFoRfW"
  }
}
```

- `cloud_content_hash`: SHA-256 of cloud-mapped fields at install time. Used for update conflict detection.
- `_environments`: Maps `requirements_fingerprint` to Managed Agents environment ID.

### Field mapping to Managed Agents API

| Our field | Managed Agents field | Notes |
|-----------|---------------------|-------|
| `name` | `name` | Direct mapping |
| `description` | `description` | Direct mapping |
| `model` + `model_speed` | `model: {id, speed}` | Object form when speed != standard |
| `tools` | `tools` | Passthrough |
| `mcp_servers` | `mcp_servers` | Passthrough |
| `skills` | `skills` | Passthrough |
| `callable_agents` | `callable_agents` | Local names resolved to agent_id via sync registry |
| Markdown body | `system` | Full body becomes the system prompt |
| `role`, `capabilities` | `metadata` | Optional |
| `voice`, `fallback_voice`, `icon`, `extra_context` | -- | NOT synced |

## Phase 2 -- Starter Agent Scaffolding

### New function: `scaffold_agents_directory`

When `scaffold_project()` creates a new project, also create an `agents/` directory with starter agent definitions appropriate for the project type.

```python
STARTER_AGENTS = {
    "game": ["game-designer", "level-designer", "narrative-writer"],
    "web": ["ux-reviewer", "security-auditor", "performance-analyst"],
    "api": ["api-designer", "documentation-writer", "test-engineer"],
    "default": ["code-reviewer"],
}

def scaffold_agents_directory(project_dir: str, tech_stack: str) -> list[str]:
    """Create agents/ directory with starter agent definitions.
    
    Returns list of created agent slugs.
    """
```

Each starter agent is a minimal markdown file:
```yaml
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
```

### Integration into `scaffold_project`

After step 8 (write .gitignore), add step 8b:
- Call `scaffold_agents_directory(project_dir, tech_stack)`
- The agents are committed along with the rest of the scaffold

### Update WORKFLOW_TEMPLATE

Add `agents/` directory to the generated WORKFLOW.md awareness. The executor agent should know agents exist.

## Phase 3 -- Cloud Agent Management

### New CLI subcommands

**`forge add <agent-name-or-id> [--project-dir <path>]`**
```python
def add_agent(agent_name_or_id: str, project_dir: str) -> dict:
    """Install a cloud agent into the project's agents/ directory.
    
    1. Call GET /v1/agents to find the agent by name or ID
    2. Translate API response to local markdown format:
       - system prompt -> markdown body
       - API fields -> YAML frontmatter
    3. Write agents/{slug}.md
    4. Compute cloud_content_hash (SHA-256 of cloud-mapped fields)
    5. Update agents/.managed-sync.json
    6. Return {slug, name, version, path}
    """
```

**`forge update <agent-slug> [--project-dir <path>] [--force]`**
```python
def update_agent(slug: str, project_dir: str, force: bool = False) -> dict:
    """Update a cloud-sourced agent to the latest version.
    
    1. Load .managed-sync.json entry for this slug
    2. Fetch latest version from cloud
    3. If cloud version == installed version: return (already up to date)
    4. Conflict check:
       - Compute current file's cloud-mapped fields hash
       - Compare with stored cloud_content_hash
       - If different and not --force: raise ConflictError with changed fields
    5. Replace cloud-mapped fields in local file
    6. Preserve Prism-specific fields (voice, icon, role, capabilities, extra_context)
    7. Update .managed-sync.json with new version + hash
    8. Return {slug, old_version, new_version, conflicts_overridden}
    """
```

**`forge publish <agent-slug> [--project-dir <path>]`**
```python
def publish_agent(slug: str, project_dir: str) -> dict:
    """Publish a local agent to the Managed Agents cloud registry.
    
    1. Parse agents/{slug}.md -> extract cloud-mapped fields
    2. If slug exists in .managed-sync.json: PATCH /v1/agents/{id}
    3. If not: POST /v1/agents
    4. Update .managed-sync.json with agent_id, version, hash
    5. Return {slug, managed_agent_id, version}
    """
```

**`forge create <agent-name> [--local] [--project-dir <path>]`**
```python
def create_agent(name: str, local: bool, project_dir: str) -> dict:
    """Create a new agent definition.
    
    If --local: scaffold a markdown file in project agents/
    If not --local: create on Managed Agents via API, then install locally
    
    Interactive: prompts for description, role, capabilities.
    """
```

### Helper functions

```python
def parse_agent_file(filepath: str) -> tuple[dict, str]:
    """Parse a guest agent markdown file.
    
    Returns (frontmatter_dict, markdown_body).
    Splits on --- delimiters, parses YAML, returns body text.
    """

def write_agent_file(filepath: str, frontmatter: dict, body: str) -> None:
    """Write a guest agent markdown file.
    
    Renders YAML frontmatter between --- delimiters, appends body.
    """

def frontmatter_to_api(frontmatter: dict, body: str) -> dict:
    """Convert local frontmatter + body to Managed Agents API payload.
    
    Maps fields per the field mapping table.
    Strips Prism-specific fields (voice, icon, etc).
    """

def api_to_frontmatter(api_response: dict) -> tuple[dict, str]:
    """Convert Managed Agents API response to local frontmatter + body.
    
    Maps system -> body, API fields -> frontmatter.
    """

def compute_cloud_content_hash(frontmatter: dict, body: str) -> str:
    """SHA-256 of cloud-mapped fields for conflict detection.
    
    Includes: name, description, model, model_speed, tools, mcp_servers,
    skills, callable_agents, and the markdown body.
    Excludes: voice, fallback_voice, icon, role, capabilities, extra_context.
    """

def load_sync_registry(agents_dir: str) -> dict:
    """Load .managed-sync.json. Returns empty dict if not found."""

def save_sync_registry(agents_dir: str, registry: dict) -> None:
    """Write .managed-sync.json atomically."""

CLOUD_MAPPED_FIELDS = {"name", "description", "model", "model_speed", "tools", 
                        "mcp_servers", "skills", "callable_agents"}
PRISM_SPECIFIC_FIELDS = {"voice", "fallback_voice", "icon", "role", "capabilities", "extra_context"}
```

### Environment auto-generation

```python
def compute_requirements_fingerprint(requirements: dict | None) -> str:
    """SHA-256 of normalized requirements section."""

def create_or_reuse_environment(
    agents_dir: str,
    fingerprint: str,
    requirements: dict,
    project_name: str,
) -> str:
    """Create or reuse a Managed Agents environment for a requirements profile.
    
    1. Check _environments in .managed-sync.json for existing env
    2. If found: return env_id
    3. If not: POST /v1/environments with mapped config
       - networking: unrestricted if internet: true, else limited
       - packages: from requirements.packages
    4. Store in _environments mapping
    5. Return env_id
    """
```

### Authentication

- Reads `ANTHROPIC_API_KEY` from environment (same as Prism)
- All cloud operations fail gracefully with clear error if key is missing
- Key is never stored in forge.py or settings.json

### CLI integration

Add subcommands to the existing argparse CLI in `forge.py`:

```
python forge.py add <agent> [--project-dir <path>]
python forge.py update <agent> [--project-dir <path>] [--force]
python forge.py publish <agent> [--project-dir <path>]
python forge.py create <name> [--local] [--project-dir <path>]
python forge.py list-cloud
python forge.py check-updates [--project-dir <path>]
```

## Testing Strategy

### New test classes

| Class | Covers |
|-------|--------|
| `TestAgentFileParsing` | `parse_agent_file`, `write_agent_file` with various frontmatter |
| `TestFieldMapping` | `frontmatter_to_api`, `api_to_frontmatter` round-trip |
| `TestCloudContentHash` | `compute_cloud_content_hash` determinism, field selection |
| `TestSyncRegistry` | `load_sync_registry`, `save_sync_registry`, missing file handling |
| `TestAddAgent` | `add_agent` with mocked API, file verification, sync registry update |
| `TestUpdateAgent` | `update_agent` clean update, conflict detection, --force, Prism field preservation |
| `TestPublishAgent` | `publish_agent` create vs update path, sync registry |
| `TestCreateAgent` | `create_agent` local and cloud paths |
| `TestScaffoldAgents` | `scaffold_agents_directory` for each tech stack type |
| `TestEnvironment` | `compute_requirements_fingerprint`, `create_or_reuse_environment` |

All tests use `tmp_path` for file I/O isolation. API calls mocked via `monkeypatch` on the HTTP client.

### Existing test updates

- `TestScaffold` should verify that `scaffold_project` now creates an `agents/` directory with starter agents
- Existing tests should not break -- new functionality is additive

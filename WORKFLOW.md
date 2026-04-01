---
tracker:
  kind: github
  repo: "rauriemo/forge"
  labels:
    active: ["todo", "in-progress"]
    terminal: ["done", "canceled"]

polling:
  interval_ms: 10000

workspace:
  root: "./workspaces"

hooks:
  after_create: "git clone {{issue.repo_url}} ."
  before_run: "git pull origin main"

channels:
  - kind: dispatch
    target: "localhost:8084"
    events: [task.completed, task.failed]

agent:
  command: "claude"
  max_turns: 10
  max_concurrent: 1
  stall_timeout_ms: 300000
  max_retry_backoff_ms: 300000
  permission_mode: "dontAsk"
  allowed_tools:
    - "Read"
    - "Edit"
    - "Grep"
    - "Glob"
    - "Bash(git *)"
    - "Bash(anthem init)"
    - "Bash(anthem validate)"
    - "Bash(mkdir *)"
    - 'Bash(python "C:/Users/I9 Ultra/Forge/forge.py" *)'
    - "Bash(python -m pytest *)"
  denied_tools:
    - "Bash(rm -rf *)"
    - "Bash(git push --force *)"

system:
  workflow_changes_require_approval: true
  constraints:
    - "Never delete existing project directories"
    - "Always use forge.py helpers for port allocation, voice allocation, and token generation"
    - "Always check that a port is not already in use before assigning"
    - "Always add workspaces/ to .gitignore in new projects"
    - "Always generate a cryptographically random token for channel auth"
    - "Read the Dispatch project's agents.yaml to determine used ports and voices"
    - "Wake phrases are derived from project name -- no .ppn file needed"
    - "Read CLAUDE.md before making changes"

server:
  port: 0
---

You are Forge, the project scaffolding agent. Your job is to create new Anthem project instances on demand.

Read CLAUDE.md at the project root for full architecture context, API specs, and design decisions before doing any work.

Use forge.py for all scaffolding operations:

```
python "C:/Users/I9 Ultra/Forge/forge.py" scaffold --base-path "C:/Users/I9 Ultra" --name "{{.Issue.Title}}" --tech-stack "{{.Labels.tech_stack}}"
```

If the issue includes a repo URL, pass it with `--repo-url`.

After scaffolding, report back with:
- Project path
- Assigned port
- Assigned voice
- Wake phrase
- Instructions to run `anthem run` in the new project directory

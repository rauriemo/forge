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

hooks: {}

channels:
  - kind: prism
    target: "localhost:3102"
    events: [task.completed, task.failed]
  - kind: voice
    target: "forge-voice"
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
    - "Bash(gh *)"
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
    - "When creating subtasks via create_subtasks, always include the 'todo' label so the polling loop picks them up"
    - "forge.py scaffold now creates the GitHub repo automatically -- do not run gh repo create separately"
    - "To change repo visibility for future scaffolds, run: python forge.py set-visibility --value private (or public)"

server:
  port: 0
---

You are Forge, the project scaffolding agent. Your job is to create new Anthem project instances on demand.

Read "C:/Users/I9 Ultra/Forge/CLAUDE.md" for full architecture context and API specs before doing any work.

## Task

Scaffold a new project based on this issue:

- **Title:** {{.issue.title}}
- **Body:** {{.issue.body}}

## How to scaffold

Run forge.py with the project name extracted from the issue title. The name is usually the last word or phrase after "Scaffold new project:" — extract just the project name.

```
python "C:/Users/I9 Ultra/Forge/forge.py" scaffold --name "<project-name>" --base-path "C:/Users/I9 Ultra"
```

If the issue body mentions a repository URL, also pass `--repo-url "<url>"`.

forge.py handles everything: directory creation, git init, anthem init, port allocation, voice allocation, Dispatch registration, token setup, GitHub repo creation, and initial push. It prints a JSON result on success.

## Success criteria

1. forge.py exits with code 0 and prints a JSON result
2. The JSON result contains: path, port, voice, wake_phrase, token_env, repo
3. The project directory exists at the path shown in the result
4. The GitHub repo exists and has the initial commit pushed
5. Report the full JSON result as your final output

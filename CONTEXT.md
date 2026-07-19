# OpenCode Workspace Rules

- **Anti-Loop Rule**: After modifying any file (via write/patch), do NOT call tool functions to read the same file again. Assume your changes are successfully written. Only re-read if a build error or linter error forces verification.
- Save your token budget by relying on the diff output instead of performing full-file reads.
- Prefer batch edits over full-file rewrites when possible.
- Use `Glob` and `Grep` for discovery, not `Read` on entire files.

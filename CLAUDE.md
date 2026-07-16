# Repository conventions

## Git / commit hygiene (mandatory)

- **Branch names:** never use a `claude/` prefix. Use plain, descriptive branch
  names (e.g. `issue-43-king-capture-fix`).
- **Commit messages:** no AI self-attribution. Do not add `Co-Authored-By: Claude`,
  `Claude-Session:`, "Generated with Claude", or similar trailers/lines. Write
  plain, human-style commit messages.

## Testing

- The suite is run with `python -m pytest test/`. Keep it green.
- Tests that depend on external binaries (e.g. the Scan engine oracle used by
  `test/test_cross_validation.py`) must auto-skip when the binary is absent, so
  the default run and CI stay green without extra setup.

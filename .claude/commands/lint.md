---
description: Run ruff linter and formatter across the entire project
allowed-tools: Bash(ruff:*), Bash(make:*)
---

# /lint

Run ruff check and format on the full codebase.

```bash
make lint
```

If there are unfixable errors, list them and suggest fixes.

# altRAG

Pointer-based skill retrieval for LLM agents. Alternative to vector DB RAG.

Instead of embedding chunks into vectors and doing similarity search, altRAG builds a deterministic pointer table mapping every heading in your skill files to its exact line number and byte offset. The agent reads the lightweight skeleton during planning, then reads only the exact sections it needs. No embeddings. No vector DB. No similarity thresholds.

## Install

```
pip install altrag
```

## Quick start

```bash
altrag setup
```

That's it. This single command:
1. Finds your skill files (checks `docs/`, `skills/`, `knowledge/`, or any `.md`/`.yaml` files)
2. Scans them into a pointer skeleton (`.skt`)
3. Generates an interactive HTML tree viewer
4. Adds the retrieval directive to your agent's config file (auto-detects which agent you use)
5. Updates `.gitignore`

Works with Claude Code, Cursor, Windsurf, Cline, GitHub Copilot, OpenAI Codex, Devin, Replit Agent, or any LLM agent that can read files.

## How it works

Your skill files:
```
docs/
  k8s-deployment.md    (195 lines)
  api-reference.md     (200 lines)
```

After `altrag setup`, the skeleton (`docs/skills.skt`) looks like:
```
@ docs/k8s-deployment.md
1   0     4662   1    195   Kubernetes Deployment Guide
2   1163  1565   42   70    Deployment Strategies
3   2110  613    82   28    Canary Deployment
...
```

When the agent needs to know about canary deployments, it reads the skeleton (~100 tokens), finds "Canary Deployment" at line 82 for 28 lines, and reads exactly that section. Not the full 195-line file. Not 5 fuzzy RAG chunks. Exactly the 28 lines it needs.

## Commands

```bash
altrag setup                  # auto-detect, scan, configure — does everything
altrag scan <path> -o out.skt # scan files/directory into skeleton
altrag tree <path>            # generate and open interactive HTML tree
altrag init [dir]             # create a skills directory with examples
```

## Agent integration

`altrag setup` automatically adds the retrieval directive to whichever agent config file exists in your project:

| Agent | Config file |
|-------|------------|
| Claude Code | `CLAUDE.md` |
| Cursor | `.cursorrules` |
| Windsurf | `.windsurfrules` |
| Cline | `.clinerules` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| OpenAI Codex | `codex.md` or `AGENTS.md` |
| Replit Agent | `replit.md` |

If none exist, it creates `CLAUDE.md`.

The directive tells the agent: read the `.skt` file to see what knowledge is available, then read only the exact section you need by its line pointer. Simple, universal, no vendor lock-in.

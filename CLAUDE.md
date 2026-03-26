# altRAG

Pointer-based skill retrieval for LLM agents. Alternative to vector DB RAG.

## When a user asks to set up altRAG in their project

Run these two commands in their project directory:

```bash
pip install altrag
altrag setup
```

That's it. `altrag setup` automatically:
1. Finds skill files (checks docs/, skills/, knowledge/, or any .md files)
2. Scans them into a pointer skeleton (.skt)
3. Generates an interactive HTML tree viewer (HUMAN.html)
4. Adds the retrieval directive to CLAUDE.md (or .cursorrules, codex.md, etc.)
5. Updates .gitignore

If the user doesn't have skill files yet:
```bash
altrag init
altrag setup
```

## How to use altRAG in a project that already has it set up

Read the .skt file to see all available skill sections with their line pointers.
Then read only the exact section you need using the line and count from the skeleton.
Never load full skill files — use the pointers for surgical retrieval.

## After modifying skill files

Re-run: `altrag scan <skills-dir> -o <skills-dir>/skills.skt`

"""
altrag CLI — scan skill files, generate pointer trees and interactive viewers.

Usage:
    altrag setup                  Auto-detect skills, scan, generate tree, configure agent
    altrag scan <path>            Scan files/directory, output .skt to stdout
    altrag tree <path>            Generate HUMAN.html and open it
    altrag init [dir]             Set up a skills directory with examples
"""

import argparse
import os
import sys
import glob as globmod

from altrag.scanner import scan_many, emit_skt, generate_html, detect_format


def find_files(path: str) -> list[str]:
    """Resolve a path to a list of scannable files."""
    if os.path.isfile(path):
        return [path]
    if os.path.isdir(path):
        files = []
        for ext in ('*.md', '*.markdown', '*.yaml', '*.yml'):
            files.extend(globmod.glob(os.path.join(path, '**', ext), recursive=True))
        return sorted(files)
    # try glob pattern
    return sorted(globmod.glob(path, recursive=True))


def cmd_scan(args):
    files = []
    for p in args.paths:
        files.extend(find_files(p))
    if not files:
        print("altrag: no skill files found", file=sys.stderr)
        sys.exit(1)

    file_data = scan_many(files, args.format)
    if not file_data:
        print("altrag: no structure found in any file", file=sys.stderr)
        sys.exit(1)

    skt = emit_skt(file_data)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(skt)
        print(f"altrag: skeleton written to {args.output} ({len(file_data)} files)", file=sys.stderr)
    else:
        sys.stdout.write(skt)


def cmd_tree(args):
    files = []
    for p in args.paths:
        files.extend(find_files(p))
    if not files:
        print("altrag: no skill files found", file=sys.stderr)
        sys.exit(1)

    file_data = scan_many(files, args.format)
    if not file_data:
        print("altrag: no structure found in any file", file=sys.stderr)
        sys.exit(1)

    html = generate_html(file_data)
    out = args.output or 'HUMAN.html'

    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"altrag: tree viewer written to {out} ({len(file_data)} files)", file=sys.stderr)

    if not args.no_open:
        import webbrowser
        webbrowser.open(os.path.abspath(out))


def cmd_init(args):
    target = args.dir or 'skills'
    os.makedirs(target, exist_ok=True)

    sample = os.path.join(target, 'example.md')
    if not os.path.exists(sample):
        with open(sample, 'w', encoding='utf-8') as f:
            f.write("""# Example Skill

This is a sample skill file for altRAG.

## Section One

Content for section one. The scanner will create a pointer
to this section with its exact line and byte offsets.

## Section Two

### Subsection A

Detailed content here.

### Subsection B

More detailed content.

## Section Three

Final section content.
""")
    print(f"altrag: initialized {target}/")
    print(f"  Next steps:")
    print(f"    altrag scan {target}          # generate .skt skeleton")
    print(f"    altrag tree {target}          # open interactive viewer")


ALTRAG_DIRECTIVE = """
## Skill Retrieval (altRAG)
This project uses altRAG for pointer-based skill retrieval.
Instead of loading full skill files, use the pointer skeleton for surgical access:
1. Read `{skt_path}` to see all available sections with their line pointers
2. Find the section relevant to your task by its title
3. Read only that section from the source file — start at line number `ln`, read `lc` lines
Never load entire skill files into context. The skeleton has the exact line ranges.
IMPORTANT: After creating, deleting, or modifying any skill file, you MUST re-run:
`altrag scan {skills_dir} -o {skt_path}`
Do this immediately — do not wait until later. Stale pointers cause wrong reads.
""".strip()

PRE_COMMIT_HOOK = '''#!/usr/bin/env bash
# altRAG pre-commit hook — re-scans skill files if any changed
SKILLS_DIR="{skills_dir}"
SKT_PATH="{skt_path}"

changed=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\\.(md|markdown|yaml|yml)$' | grep -Ev '^(README|CHANGELOG)\\.md$' || true)
if [ -n "$changed" ]; then
    if command -v altrag &>/dev/null; then
        altrag scan "$SKILLS_DIR" -o "$SKT_PATH"
        git add "$SKT_PATH"
    fi
fi
'''


def cmd_setup(args):
    """Auto-detect everything, scan, generate tree, configure agent directives."""

    # 1. find skill files — check common locations
    candidates = ['docs', 'skills', 'knowledge', 'wiki', '.']
    skills_dir = None
    files = []

    if args.path:
        files = find_files(args.path)
        skills_dir = args.path
    else:
        for d in candidates:
            if os.path.isdir(d):
                found = find_files(d)
                if found and d != '.':
                    files = found
                    skills_dir = d
                    break
        if not files:
            # fallback: scan current directory but only top-level .md files
            top_md = globmod.glob('*.md')
            # exclude common non-skill files
            skip = {'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'LICENSE.md'}
            top_md = [f for f in top_md if f not in skip]
            if top_md:
                files = top_md
                skills_dir = '.'

    if not files:
        print("altrag: no skill files found. Create some .md files or run: altrag init", file=sys.stderr)
        sys.exit(1)

    print(f"altrag: found {len(files)} skill file(s) in {skills_dir}/")

    # 2. scan
    file_data = scan_many(files)
    if not file_data:
        print("altrag: no structure found in any file", file=sys.stderr)
        sys.exit(1)

    total_sections = sum(len(s) for _, s in file_data)
    print(f"altrag: {total_sections} sections indexed across {len(file_data)} files")

    # 3. write .skt
    skt_path = os.path.join(skills_dir, 'skills.skt')
    skt = emit_skt(file_data)
    os.makedirs(os.path.dirname(skt_path) or '.', exist_ok=True)
    with open(skt_path, 'w', encoding='utf-8') as f:
        f.write(skt)
    print(f"altrag: skeleton -> {skt_path}")

    # 4. generate HUMAN.html
    try:
        html = generate_html(file_data)
        html_path = 'HUMAN.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"altrag: tree viewer -> {html_path}")
    except FileNotFoundError:
        print("altrag: template.html not found, skipping HTML generation", file=sys.stderr)

    # 5. add directive to agent config files
    directive = ALTRAG_DIRECTIVE.format(skt_path=skt_path, skills_dir=skills_dir)

    # every known agent instruction file
    agent_files = [
        'CLAUDE.md',                          # Claude Code
        '.cursorrules',                       # Cursor
        '.windsurfrules',                     # Windsurf / Codeium
        '.clinerules',                        # Cline
        'codex.md',                           # OpenAI Codex CLI
        'AGENTS.md',                          # OpenAI Codex
        '.github/copilot-instructions.md',    # GitHub Copilot
        'replit.md',                          # Replit Agent
        'CONVENTIONS.md',                     # Various agents
    ]

    configured = []
    for af in agent_files:
        if os.path.isfile(af):
            with open(af, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'altRAG' in content or 'altrag' in content:
                print(f"altrag: {af} already configured, skipping")
                configured.append(af)
                continue
            with open(af, 'a', encoding='utf-8') as f:
                f.write('\n\n' + directive + '\n')
            print(f"altrag: directive added to {af}")
            configured.append(af)

    if not configured:
        # no agent config found — create CLAUDE.md as default
        with open('CLAUDE.md', 'w', encoding='utf-8') as f:
            f.write(directive + '\n')
        print(f"altrag: created CLAUDE.md with directive")
        configured.append('CLAUDE.md')

    # 6. update .gitignore
    gitignore = '.gitignore'
    ignore_entries = ['*.skt', 'HUMAN.html']
    if os.path.isfile(gitignore):
        with open(gitignore, 'r', encoding='utf-8') as f:
            existing = f.read()
        additions = [e for e in ignore_entries if e not in existing]
        if additions:
            with open(gitignore, 'a', encoding='utf-8') as f:
                f.write('\n# altRAG generated\n' + '\n'.join(additions) + '\n')
            print(f"altrag: updated .gitignore")
    else:
        with open(gitignore, 'w', encoding='utf-8') as f:
            f.write('# altRAG generated\n' + '\n'.join(ignore_entries) + '\n')
        print(f"altrag: created .gitignore")

    # 7. install git pre-commit hook (if in a git repo)
    git_hooks_dir = os.path.join('.git', 'hooks')
    if os.path.isdir(git_hooks_dir):
        hook_path = os.path.join(git_hooks_dir, 'pre-commit')
        hook_content = PRE_COMMIT_HOOK.format(
            skills_dir=skills_dir.replace('\\', '/'),
            skt_path=skt_path.replace('\\', '/'),
        )

        if os.path.isfile(hook_path):
            with open(hook_path, 'r', encoding='utf-8') as f:
                existing = f.read()
            if 'altRAG' in existing or 'altrag' in existing:
                print(f"altrag: pre-commit hook already configured")
            else:
                # append to existing hook
                with open(hook_path, 'a', encoding='utf-8') as f:
                    f.write('\n' + hook_content)
                print(f"altrag: appended to existing pre-commit hook")
        else:
            with open(hook_path, 'w', encoding='utf-8') as f:
                f.write(hook_content)
            os.chmod(hook_path, 0o755)
            print(f"altrag: installed pre-commit hook")

    print(f"\naltrag: ready. Your agent can now read {skt_path} for surgical skill retrieval.")


def main():
    parser = argparse.ArgumentParser(
        prog='altrag',
        description='Pointer-based skill retrieval for LLM agents. Alternative to RAG.',
        epilog=(
            'examples:\n'
            '  altrag setup                 Auto-detect skills, scan, generate tree\n'
            '  altrag scan docs/ -o docs/skills.skt\n'
            '  altrag tree skills/          Open interactive HTML viewer\n'
            '  altrag init                  Create example skill files\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='command')

    # scan
    p_scan = sub.add_parser('scan', help='Scan skill files and output .skt skeleton')
    p_scan.add_argument('paths', nargs='+', help='Files, directories, or glob patterns')
    p_scan.add_argument('-o', '--output', help='Write to file instead of stdout')
    p_scan.add_argument('-f', '--format', default='auto', choices=['auto', 'md', 'yaml'])

    # tree
    p_tree = sub.add_parser('tree', help='Generate interactive HTML tree viewer')
    p_tree.add_argument('paths', nargs='+', help='Files, directories, or glob patterns')
    p_tree.add_argument('-o', '--output', help='Output HTML path (default: HUMAN.html)')
    p_tree.add_argument('-f', '--format', default='auto', choices=['auto', 'md', 'yaml'])
    p_tree.add_argument('--no-open', action='store_true', help='Do not open in browser')

    # init
    p_init = sub.add_parser('init', help='Set up a skills directory with examples')
    p_init.add_argument('dir', nargs='?', help='Target directory (default: skills)')

    # setup
    p_setup = sub.add_parser('setup', help='Auto-detect skills, scan, generate tree, configure agent')
    p_setup.add_argument('path', nargs='?', help='Skills directory (auto-detected if omitted)')

    args = parser.parse_args()

    if args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'tree':
        cmd_tree(args)
    elif args.command == 'init':
        cmd_init(args)
    elif args.command == 'setup':
        cmd_setup(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

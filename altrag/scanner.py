"""
altrag.scanner — Core scanning engine.

Scans skill files (Markdown, YAML) and extracts a hierarchical pointer tree
mapping byte offsets and line numbers to structural headings.
"""

import importlib.resources
import json
import os
import sys
import warnings


def _decode_line(raw: bytes, path: str, line_num: int) -> str:
    """Decode a line as UTF-8, warning on encoding issues instead of silently replacing."""
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        warnings.warn(f"{path}:{line_num}: invalid UTF-8 bytes, replaced with U+FFFD", stacklevel=2)
        return raw.decode('utf-8', errors='replace')


def is_hrule(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 3:
        return False
    ch = stripped[0]
    if ch not in ('-', '*', '_'):
        return False
    return all(c == ch for c in stripped)


def is_bold_heading(line: str) -> str | None:
    stripped = line.strip()
    if len(stripped) < 5:
        return None
    if not stripped.startswith('**') or not stripped.endswith('**'):
        return None
    inner = stripped[2:-2]
    if '**' in inner or len(inner) == 0:
        return None
    return inner


def skip_front_matter(lines: list[bytes]) -> int:
    if not lines or lines[0].rstrip(b'\r\n') != b'---':
        return 0
    for i in range(1, len(lines)):
        if lines[i].rstrip(b'\r\n') == b'---':
            return i + 1
    return 0


def detect_format(path: str) -> str:
    if path.endswith('.yaml') or path.endswith('.yml'):
        return 'yaml'
    return 'md'


def scan_md(path: str) -> list[dict]:
    """Scan a Markdown file and return list of section dicts."""
    with open(path, 'rb') as f:
        raw = f.read()

    file_size = len(raw)
    lines_raw = raw.split(b'\n')
    start_idx = skip_front_matter(lines_raw)

    sections = []
    in_code = False
    anchor = 0

    offsets = []
    off = 0
    for lr in lines_raw:
        offsets.append(off)
        off += len(lr) + 1

    for idx in range(start_idx, len(lines_raw)):
        line = _decode_line(lines_raw[idx], path, idx + 1).rstrip('\r')
        line_num = idx + 1
        byte_off = offsets[idx]

        if line.startswith('```') or line.startswith('~~~'):
            in_code = not in_code
            continue
        if in_code:
            continue

        if line.startswith('#'):
            depth = 0
            while depth < len(line) and line[depth] == '#':
                depth += 1
            if 1 <= depth <= 6 and depth < len(line) and line[depth] == ' ':
                sections.append({
                    'depth': depth, 'offset': byte_off,
                    'line': line_num, 'title': line[depth + 1:].strip(),
                })
                anchor = depth
                continue

        btitle = is_bold_heading(line)
        if btitle is not None:
            d = anchor + 1 if 0 < anchor < 6 else (6 if anchor >= 6 else 1)
            sections.append({
                'depth': d, 'offset': byte_off,
                'line': line_num, 'title': btitle,
            })
            continue

        if len(line.strip()) >= 3 and is_hrule(line):
            d = anchor if anchor > 0 else 1
            sections.append({
                'depth': d, 'offset': byte_off,
                'line': line_num, 'title': '---',
            })
            continue

    total_lines = len(lines_raw)
    _calc_bounds(sections, file_size, total_lines)
    return sections


def scan_yaml(path: str) -> list[dict]:
    """Scan a YAML file using indentation depth as heading levels."""
    with open(path, 'rb') as f:
        raw = f.read()

    file_size = len(raw)
    lines_raw = raw.split(b'\n')

    sections = []
    indent_unit = 2
    indent_found = False
    start_idx = 0

    if lines_raw and lines_raw[0].rstrip(b'\r\n') == b'---':
        start_idx = 1

    offsets = []
    off = 0
    for lr in lines_raw:
        offsets.append(off)
        off += len(lr) + 1

    for idx in range(start_idx, len(lines_raw)):
        line = _decode_line(lines_raw[idx], path, idx + 1).rstrip('\r')
        line_num = idx + 1
        byte_off = offsets[idx]

        stripped = line.lstrip(' ')
        spaces = len(line) - len(stripped)

        if not stripped or stripped.startswith('#'):
            continue
        if stripped.startswith('- ') or stripped == '-':
            continue

        if not indent_found and spaces > 0:
            indent_unit = spaces
            indent_found = True

        if indent_found and spaces > 0 and spaces % indent_unit != 0:
            warnings.warn(
                f"{path}:{line_num}: indentation ({spaces} spaces) is not a multiple "
                f"of the base indent ({indent_unit} spaces)",
                stacklevel=2,
            )

        colon_pos = stripped.find(':')
        if colon_pos > 0:
            key = stripped[:colon_pos].strip()
            if key and not key.startswith('-'):
                depth = spaces // indent_unit + 1 if indent_unit > 0 else 1
                sections.append({
                    'depth': depth, 'offset': byte_off,
                    'line': line_num, 'title': key,
                })

    total_lines = len(lines_raw)
    _calc_bounds(sections, file_size, total_lines)
    return sections


def _calc_bounds(sections, file_size, total_lines):
    """Calculate byte length and line count for each section.

    total_lines is len(raw.split(b'\\n')), which includes a trailing empty
    element when the file ends with \\n.  We use total_lines (not +1) as the
    sentinel so line_count reflects actual content lines.
    """
    for i, sec in enumerate(sections):
        end_off = file_size
        end_ln = total_lines
        for j in range(i + 1, len(sections)):
            if sections[j]['depth'] <= sec['depth']:
                end_off = sections[j]['offset']
                end_ln = sections[j]['line']
                break
        sec['length'] = end_off - sec['offset']
        sec['line_count'] = max(1, end_ln - sec['line'])


def scan(path: str, fmt: str = 'auto') -> list[dict]:
    """Scan a single file. Auto-detects format from extension."""
    if fmt == 'auto':
        fmt = detect_format(path)
    return scan_yaml(path) if fmt == 'yaml' else scan_md(path)


def scan_many(paths: list[str], fmt: str = 'auto') -> list[tuple[str, list[dict]]]:
    """Scan multiple files. Returns list of (path, sections) tuples."""
    results = []
    for path in paths:
        try:
            sections = scan(path, fmt)
            if sections:
                results.append((path, sections))
                print(f"  {path}: {len(sections)} sections", file=sys.stderr)
            else:
                print(f"  {path}: 0 sections (no headings found)", file=sys.stderr)
        except Exception as e:
            print(f"altrag: error processing {path}: {e}", file=sys.stderr)
    return results


def build_tree(sections: list[dict]) -> list[dict]:
    """Convert flat section list to nested tree."""
    root = []
    stack = [{'d': 0, 'ch': root}]
    for sec in sections:
        node = {
            'd': sec['depth'], 't': sec['title'],
            'off': sec['offset'], 'len': sec['length'],
            'ln': sec['line'], 'lc': sec['line_count'],
            'ch': []
        }
        while stack[-1]['d'] >= sec['depth']:
            stack.pop()
        stack[-1]['ch'].append(node)
        stack.append({'d': sec['depth'], 'ch': node['ch']})
    return root


def emit_skt(file_data: list[tuple[str, list[dict]]]) -> str:
    """Generate .skt skeleton text from scanned file data."""
    lines = [
        "# altRAG Pointer Skeleton",
        "# This file maps every section in your skill files to its exact location.",
        "# To retrieve a section, read the file starting at line <ln> for <lc> lines.",
        "# Columns: depth, byte_offset, byte_length, line_number, line_count, title",
        "# Files are grouped under @ headers.",
    ]
    for path, sections in file_data:
        lines.append(f"\n@ {path}")
        for s in sections:
            title = s['title'].replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
            lines.append(f"{s['depth']}\t{s['offset']}\t{s['length']}\t{s['line']}\t{s['line_count']}\t{title}")
    return '\n'.join(lines) + '\n'


def generate_html(file_data: list[tuple[str, list[dict]]]) -> str:
    """Generate interactive HUMAN.html from scanned file data."""
    tree_data = []
    total_sections = 0
    for path, sections in file_data:
        tree = build_tree(sections)
        tree_data.append({'path': path, 'tree': tree, 'count': len(sections)})
        total_sections += len(sections)

    tj = json.dumps(tree_data, ensure_ascii=False)

    # load template.html via importlib.resources (works with installed packages and zips)
    try:
        ref = importlib.resources.files('altrag').joinpath('template.html')
        t = ref.read_text(encoding='utf-8')
    except (FileNotFoundError, TypeError):
        raise FileNotFoundError("template.html not found in altrag package")

    return (t
        .replace('__TREE_JSON__', tj)
        .replace('__TOTAL_FILES__', str(len(tree_data)))
        .replace('__TOTAL_SECTIONS__', str(total_sections)))

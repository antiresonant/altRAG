"""Tests for altrag.scanner — core scanning engine."""

import os
import tempfile

from altrag.scanner import scan_md, scan_yaml, emit_skt, scan_many, build_tree


def _write_tmp(content: str, suffix: str = '.md') -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


def _write_tmp_bytes(content: bytes, suffix: str = '.md') -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'wb') as f:
        f.write(content)
    return path


SAMPLE_MD = """\
# Top Level

Intro paragraph.

## Section A

Content A.

### Subsection A1

Detail A1.

## Section B

Content B.
"""

SAMPLE_YAML = """\
---
database:
  host: localhost
  port: 5432
  credentials:
    user: admin
    password: secret
cache:
  enabled: true
"""


class TestScanMd:
    def test_basic_headings(self):
        path = _write_tmp(SAMPLE_MD)
        try:
            sections = scan_md(path)
            titles = [s['title'] for s in sections]
            assert titles == ['Top Level', 'Section A', 'Subsection A1', 'Section B']
        finally:
            os.unlink(path)

    def test_depths(self):
        path = _write_tmp(SAMPLE_MD)
        try:
            sections = scan_md(path)
            depths = [s['depth'] for s in sections]
            assert depths == [1, 2, 3, 2]
        finally:
            os.unlink(path)

    def test_line_numbers(self):
        path = _write_tmp(SAMPLE_MD)
        try:
            sections = scan_md(path)
            assert sections[0]['line'] == 1  # # Top Level
            assert sections[1]['line'] == 5  # ## Section A
        finally:
            os.unlink(path)

    def test_line_counts(self):
        path = _write_tmp(SAMPLE_MD)
        try:
            sections = scan_md(path)
            # Section A (depth 2) spans from line 5 until Section B (depth 2) at line 13
            assert sections[1]['line_count'] == 8
            # Subsection A1 (depth 3) spans from line 9 until Section B (depth 2) at line 13
            assert sections[2]['line_count'] == 4
        finally:
            os.unlink(path)

    def test_front_matter_skipped(self):
        content = "---\ntitle: Test\n---\n# Heading\n\nBody.\n"
        path = _write_tmp(content)
        try:
            sections = scan_md(path)
            assert len(sections) == 1
            assert sections[0]['title'] == 'Heading'
        finally:
            os.unlink(path)

    def test_code_blocks_ignored(self):
        content = "# Real\n\n```\n# Not a heading\n```\n\n## Also Real\n"
        path = _write_tmp(content)
        try:
            sections = scan_md(path)
            titles = [s['title'] for s in sections]
            assert titles == ['Real', 'Also Real']
        finally:
            os.unlink(path)

    def test_single_line_file(self):
        path = _write_tmp("# Only\n")
        try:
            sections = scan_md(path)
            assert len(sections) == 1
            assert sections[0]['line_count'] == 1
        finally:
            os.unlink(path)

    def test_single_heading_no_trailing_newline(self):
        path = _write_tmp("# Only")
        try:
            sections = scan_md(path)
            assert len(sections) == 1
            assert sections[0]['line_count'] == 1
        finally:
            os.unlink(path)

    def test_empty_file(self):
        path = _write_tmp("")
        try:
            sections = scan_md(path)
            assert sections == []
        finally:
            os.unlink(path)

    def test_bom_stripped(self):
        """UTF-8 BOM should not prevent first heading detection."""
        bom = b'\xef\xbb\xbf'
        path = _write_tmp_bytes(bom + b"# Title\n\n## Section\n")
        try:
            sections = scan_md(path)
            assert len(sections) == 2
            assert sections[0]['title'] == 'Title'
        finally:
            os.unlink(path)

    def test_crlf_line_endings(self):
        """Windows CRLF files should scan correctly."""
        path = _write_tmp_bytes(b"# Top\r\n\r\n## Sub\r\nContent.\r\n")
        try:
            sections = scan_md(path)
            assert len(sections) == 2
            assert sections[0]['title'] == 'Top'
            assert sections[1]['title'] == 'Sub'
        finally:
            os.unlink(path)

    def test_fence_type_mismatch(self):
        """Opening with ``` and closing with ~~~ should NOT toggle code mode."""
        content = "# Real\n\n```\n# Hidden\n~~~\n\n# Also Hidden\n\n```\n\n## After Code\n"
        path = _write_tmp(content)
        try:
            sections = scan_md(path)
            titles = [s['title'] for s in sections]
            assert titles == ['Real', 'After Code']
        finally:
            os.unlink(path)


class TestScanYaml:
    def test_basic_keys(self):
        path = _write_tmp(SAMPLE_YAML, suffix='.yaml')
        try:
            sections = scan_yaml(path)
            titles = [s['title'] for s in sections]
            assert 'database' in titles
            assert 'host' in titles
            assert 'cache' in titles
        finally:
            os.unlink(path)

    def test_nesting_depth(self):
        path = _write_tmp(SAMPLE_YAML, suffix='.yaml')
        try:
            sections = scan_yaml(path)
            by_title = {s['title']: s for s in sections}
            assert by_title['database']['depth'] == 1
            assert by_title['host']['depth'] == 2
            assert by_title['user']['depth'] == 3
        finally:
            os.unlink(path)


class TestEmitSkt:
    def test_output_format(self):
        path = _write_tmp(SAMPLE_MD)
        try:
            sections = scan_md(path)
            file_data = [(path, sections)]
            skt = emit_skt(file_data)
            assert skt.startswith('# altRAG Pointer Skeleton')
            assert f'@ {path.replace(chr(92), "/")}' in skt
            # each section line should have 6 tab-separated columns
            data_lines = [l for l in skt.split('\n') if l and not l.startswith('#') and not l.startswith('@') and not l.startswith('\n')]
            for line in data_lines:
                parts = line.split('\t')
                assert len(parts) == 6, f"Expected 6 columns, got {len(parts)}: {line!r}"
        finally:
            os.unlink(path)

    def test_title_sanitization(self):
        """Titles with tabs/newlines should be sanitized in TSV output."""
        path = _write_tmp("# Clean Title\n\nBody.\n")
        try:
            sections = scan_md(path)
            # Manually inject a dirty title to test sanitization
            sections[0]['title'] = "Has\tTab\nNewline"
            file_data = [(path, sections)]
            skt = emit_skt(file_data)
            # no raw tabs beyond the column separators
            data_lines = [l for l in skt.split('\n') if l and not l.startswith('#') and not l.startswith('@')]
            for line in data_lines:
                parts = line.split('\t')
                assert len(parts) == 6, f"Dirty title broke TSV: {line!r}"
        finally:
            os.unlink(path)


class TestScanMany:
    def test_multiple_files(self):
        p1 = _write_tmp("# File One\n\n## Section\n")
        p2 = _write_tmp("# File Two\n")
        try:
            results = scan_many([p1, p2])
            assert len(results) == 2
        finally:
            os.unlink(p1)
            os.unlink(p2)

    def test_skips_empty(self):
        p1 = _write_tmp("# Has Heading\n")
        p2 = _write_tmp("No headings here.\n")
        try:
            results = scan_many([p1, p2])
            assert len(results) == 1
        finally:
            os.unlink(p1)
            os.unlink(p2)


class TestBuildTree:
    def test_nesting(self):
        path = _write_tmp(SAMPLE_MD)
        try:
            sections = scan_md(path)
            tree = build_tree(sections)
            assert len(tree) == 1  # one root node
            assert tree[0]['t'] == 'Top Level'
            assert len(tree[0]['ch']) == 2  # Section A, Section B
            assert tree[0]['ch'][0]['ch'][0]['t'] == 'Subsection A1'
        finally:
            os.unlink(path)

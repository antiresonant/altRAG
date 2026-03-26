"""Tests for altrag.cli — command-line interface."""

import os
import subprocess
import sys
import tempfile


def _run(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, '-m', 'altrag', *args],
        capture_output=True, text=True, cwd=cwd,
    )


class TestInit:
    def test_creates_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'skills')
            r = _run('init', target)
            assert r.returncode == 0
            assert os.path.isfile(os.path.join(target, 'example.md'))

    def test_custom_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'docs')
            r = _run('init', target)
            assert r.returncode == 0
            assert os.path.isdir(target)


class TestScan:
    def test_scan_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = os.path.join(tmp, 'test.md')
            with open(md, 'w') as f:
                f.write("# Title\n\n## Section\n\nBody.\n")
            r = _run('scan', md)
            assert r.returncode == 0
            assert '@ ' in r.stdout
            assert 'Title' in r.stdout
            assert 'Section' in r.stdout

    def test_scan_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ['a.md', 'b.md']:
                with open(os.path.join(tmp, name), 'w') as f:
                    f.write(f"# {name}\n\n## Sub\n")
            r = _run('scan', tmp)
            assert r.returncode == 0
            assert 'a.md' in r.stdout
            assert 'b.md' in r.stdout

    def test_scan_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = os.path.join(tmp, 'test.md')
            skt = os.path.join(tmp, 'out.skt')
            with open(md, 'w') as f:
                f.write("# Hello\n")
            r = _run('scan', md, '-o', skt)
            assert r.returncode == 0
            assert os.path.isfile(skt)
            with open(skt) as f:
                content = f.read()
            assert 'Hello' in content

    def test_scan_no_files_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run('scan', os.path.join(tmp, 'nonexistent'))
            assert r.returncode != 0

    def test_scan_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            yml = os.path.join(tmp, 'config.yaml')
            with open(yml, 'w') as f:
                f.write("server:\n  host: localhost\n  port: 8080\n")
            r = _run('scan', yml)
            assert r.returncode == 0
            assert 'server' in r.stdout


class TestTree:
    def test_tree_generates_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = os.path.join(tmp, 'test.md')
            with open(md, 'w') as f:
                f.write("# Title\n\n## Section\n\nBody.\n")
            out = os.path.join(tmp, 'tree.html')
            r = _run('tree', md, '-o', out, '--no-open')
            assert r.returncode == 0
            assert os.path.isfile(out)
            with open(out, encoding='utf-8') as f:
                html = f.read()
            assert 'Title' in html
            assert 'Section' in html

    def test_tree_no_files_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run('tree', os.path.join(tmp, 'nonexistent'), '--no-open')
            assert r.returncode != 0


class TestSetup:
    def test_setup_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            # create a skills dir with content
            skills = os.path.join(tmp, 'skills')
            os.makedirs(skills)
            with open(os.path.join(skills, 'demo.md'), 'w') as f:
                f.write("# Demo\n\n## Part One\n\nContent.\n\n## Part Two\n\nMore.\n")

            r = _run('setup', 'skills', cwd=tmp)
            assert r.returncode == 0

            # .skt should exist
            skt_path = os.path.join(skills, 'skills.skt')
            assert os.path.isfile(skt_path)

            with open(skt_path) as f:
                skt = f.read()
            assert 'Demo' in skt
            assert 'Part One' in skt

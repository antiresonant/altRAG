# Changelog

## 0.1.1 (2026-03-26)

### Fixed
- `fetch.sh`: use `$TMPDIR`/`$TEMP` with trap cleanup instead of hardcoded `/tmp`
- Pre-commit hook: `grep -v README` no longer drops files like `API_README.md`
- Pre-commit hook: stderr no longer suppressed — errors are now visible
- Pre-commit hook: written in binary mode to avoid CRLF on Windows
- `scanner.py`: warn on invalid UTF-8 instead of silently replacing
- `scanner.py`: sanitize heading titles in TSV output (strip tabs/newlines)
- `scanner.py`: strip UTF-8 BOM so first heading is detected on Windows-edited files
- `scanner.py`: code fence type tracking — mismatched ``` vs ~~~ no longer breaks detection
- `scanner.py`: normalize paths to forward slashes in .skt output for cross-platform portability
- `_calc_bounds`: fix off-by-one for last section; guarantee `line_count >= 1`
- `pyproject.toml`: fixed GitHub URLs to point to correct repo (antiresonant/altRAG)
- `pyproject.toml`: removed `scan.c` from package-data (not a runtime file)
- `cli.py`: normalize paths in CLAUDE.md directive to forward slashes (cross-platform)

### Added
- `altrag/__main__.py` — `python -m altrag` now works
- Test suite: `tests/test_scanner.py`, `tests/test_cli.py`
- CI: GitHub Actions matrix across Python 3.10–3.13 × ubuntu/macos/windows
- `MANIFEST.in` to guarantee `template.html`, `README.md`, `LICENSE` are packaged
- CLI epilog with usage examples
- Per-file section count in scan output; warning on 0-section files
- YAML scanner: warning on inconsistent indentation
- Single-sourced version via `importlib.metadata`
- `importlib.resources` for loading `template.html` (works with zips/wheels)

### Changed
- `pyproject.toml`: added explicit `dependencies = []` and `[dev]` optional group

## 0.1.0 (2025-03-22)

Initial release: pointer-based skill retrieval for LLM agents.

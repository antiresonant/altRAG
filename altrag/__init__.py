"""altRAG — Pointer-based skill retrieval for LLM agents."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("altrag")
except PackageNotFoundError:
    __version__ = "0.1.1"  # fallback for editable/dev installs

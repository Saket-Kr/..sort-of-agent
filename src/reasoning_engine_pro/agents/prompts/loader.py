"""Prompt loader utility."""

import string
from collections import defaultdict
from pathlib import Path
from typing import Optional


class _SafeDict(defaultdict):
    """Dict that returns the key placeholder for missing keys instead of raising."""

    def __missing__(self, key: str) -> str:
        return ""


class PromptLoader:
    """Utility for loading prompt templates."""

    _EXTENSIONS = (".md", ".txt")

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize prompt loader.

        Args:
            templates_dir: Directory containing prompt templates.
                          Defaults to prompts/templates in this package.
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        self._templates_dir = templates_dir

    def load(self, name: str) -> str:
        """Load a prompt template by name (tries .md then .txt)."""
        for ext in self._EXTENSIONS:
            template_path = self._templates_dir / f"{name}{ext}"
            if template_path.exists():
                return template_path.read_text()
        raise FileNotFoundError(
            f"Prompt template not found: {self._templates_dir / name}"
        )

    def load_with_vars(self, name: str, **kwargs: str) -> str:
        """Load a prompt template and safely substitute variables.

        Missing template variables are replaced with empty strings instead
        of raising KeyError. This is safer than str.format() for prompts
        that may contain curly braces in code examples.
        """
        template = self.load(name)
        return template.format_map(_SafeDict(str, **kwargs))

"""Prompt loader utility."""

from pathlib import Path
from typing import Optional


class PromptLoader:
    """Utility for loading prompt templates."""

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
        """
        Load a prompt template by name.

        Args:
            name: Template name (without .txt extension)

        Returns:
            Template content
        """
        template_path = self._templates_dir / f"{name}.txt"
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        return template_path.read_text()

    def load_with_vars(self, name: str, **kwargs: str) -> str:
        """
        Load a prompt template and substitute variables.

        Args:
            name: Template name
            **kwargs: Variables to substitute

        Returns:
            Template content with variables substituted
        """
        template = self.load(name)
        return template.format(**kwargs)

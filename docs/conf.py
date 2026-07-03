"""Sphinx configuration. https://www.sphinx-doc.org/en/master/usage/configuration.html."""

import sys
from pathlib import Path

# Make the src-layout package importable for autodoc (works without an install too).
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

project = "Project Docs"  # TODO(/onboard): your project name
author = "Your Name"  # TODO(/onboard)
project_copyright = "YEAR, Your Name"  # TODO(/onboard)

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # parse google-style docstrings
    "sphinx.ext.viewcode",
    "myst_parser",  # author docs in Markdown
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False

myst_enable_extensions = ["colon_fence", "deflist"]

exclude_patterns = ["_build"]

html_theme = "furo"

import os
import sys

# Import the chess module.
sys.path.insert(0, os.path.abspath("../.."))
import draughts

# Do not resolve these.
# autodoc_type_aliases = {
#     "Square": "chess.Square",
#     "Color": "chess.Color",
#     "PieceType": "chess.PieceType",
#     "Bitboard": "chess.Bitboard",
#     "IntoSquareSet": "chess.IntoSquareSet",
# }

# Autodoc.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.jquery",
    "myst_parser",
]
autodoc_member_order = "bysource"
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# The suffix of source filenames.
source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "markdown",
    ".md": "markdown",
}

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "py-draughts"
copyright = "2023-2024, Michal Skibinski"

# The version.
try:
    version = draughts.__version__
    release = draughts.__version__
except AttributeError:
    version = "1.5.8"
    release = "1.5.8"


myst_enable_extensions = [
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
]
# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# The theme to use for HTML and HTML Help pages. See the documentation for
# a list of built-in themes.
html_theme = "sphinx_rtd_theme"

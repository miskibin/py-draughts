import sys
import os

# Import the chess module.
sys.path.insert(0, os.path.abspath(".."))
import checkers

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
]
autodoc_member_order = "bysource"
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# The suffix of source filenames.
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "fast-checkers"
copyright = "2023, Michal Skibinski"

# The version.
version = checkers.__version__
release = checkers.__version__

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# The theme to use for HTML and HTML Help pages. See the documentation for
# a list of built-in themes.
html_theme = "sphinx_rtd_theme"

import os
import sys

sys.path.insert(0, os.path.abspath("../.."))
import draughts

# Project information
project = "py-draughts"
copyright = "2023-2026, Michał Skibiński"
author = "Michał Skibiński"

try:
    version = draughts.__version__
    release = draughts.__version__
except AttributeError:
    version = "1.7.1"
    release = "1.7.1"

# Extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx_sitemap",
    "sphinxext.opengraph",
    "myst_parser",
]

# SEO: canonical site root for sitemap and OpenGraph
html_baseurl = "https://miskibin.github.io/py-draughts/"
sitemap_url_scheme = "{link}"

# OpenGraph / social cards
ogp_site_url = "https://miskibin.github.io/py-draughts/"
ogp_site_name = "py-draughts"
ogp_image = "https://miskibin.github.io/py-draughts/_static/speed_comparison.png"
ogp_image_alt = "py-draughts vs pydraughts speed comparison — up to 460x faster"
ogp_description_length = 200
ogp_type = "website"
ogp_enable_meta_description = True
ogp_custom_meta_tags = [
    '<meta name="keywords" content="draughts, checkers, python, international draughts, frisian draughts, russian draughts, brazilian draughts, american checkers, antidraughts, breakthrough, frysk, bitboard, pdn, fen, alpha-beta, hub protocol, game engine, board game ai, pydraughts alternative">',
    '<meta name="twitter:card" content="summary_large_image">',
]

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_type_aliases = {
    "StandardBoard": "draughts.StandardBoard",
    "AmericanBoard": "draughts.AmericanBoard",
    "FrisianBoard": "draughts.FrisianBoard",
    "RussianBoard": "draughts.RussianBoard",
    "Board": "draughts.Board",
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Source files
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
master_doc = "index"
exclude_patterns = ["_build"]

# MyST options
myst_enable_extensions = [
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "smartquotes",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3

# Pygments
pygments_style = "friendly"
pygments_dark_style = "monokai"

# HTML theme
html_theme = "furo"
html_title = f"py-draughts {release}"
html_static_path = ["_static"]
html_extra_path = ["_extra"]
html_css_files = ["custom.css"]
html_show_sourcelink = False
html_show_sphinx = False

html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "top_of_page_buttons": ["view", "edit"],
    "source_repository": "https://github.com/miskibin/py-draughts/",
    "source_branch": "main",
    "source_directory": "docs/source/",
    "light_css_variables": {
        "color-brand-primary": "#0f766e",
        "color-brand-content": "#0f766e",
        "color-brand-visited": "#0f766e",
        "font-stack": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font-stack--monospace": "'JetBrains Mono', 'Fira Code', SFMono-Regular, Menlo, Consolas, monospace",
        "color-admonition-background": "transparent",
    },
    "dark_css_variables": {
        "color-brand-primary": "#2dd4bf",
        "color-brand-content": "#2dd4bf",
        "color-brand-visited": "#2dd4bf",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/miskibin/py-draughts",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/py-draughts/",
            "html": """<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm-1.7 4.5h3.4v9h-3.4v-9zm0 11h3.4v3.4h-3.4v-3.4z"/></svg>""",
            "class": "",
        },
    ],
}

# sphinx-copybutton options
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True
copybutton_only_copy_prompt_lines = True
copybutton_remove_prompts = True

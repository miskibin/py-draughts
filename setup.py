from pathlib import Path

import setuptools

from checkers.__init__ import __doc__, __version__

this_directory = Path(__file__).parent
long_description = (this_directory / "readme.rst").read_text()

setuptools.setup(
    name="fast-checkers",
    version=__version__,
    author="Michał Skibiński",
    author_email="mskibinski109@gmail.com",
    files_to_include=["checkers"],
    description=__doc__.replace("\n", " ").strip(),
    long_description=long_description,
    # rst
    long_description_content_type="text/x-rst",
    packages=setuptools.find_packages(),
    license="GPL-3.0+",
    keywords="checkers AI mini-max droughts, game, board",
    url="https://github.com/michalskibinski109/checkers",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Games/Entertainment :: Board Games",
        "Topic :: Games/Entertainment :: Turn Based Strategy",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Typing :: Typed",
    ],
    project_urls={
        "Documentation": "https://michalskibinski109.github.io/checkers/index.html",
    },
    python_requires=">=3.10",
)

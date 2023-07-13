from pathlib import Path

import setuptools

from draughts.__init__ import __doc__, __version__

this_directory = Path(__file__).parent
long_description = (this_directory / "readme.md").read_text()

with open(this_directory / "requirements.txt") as f:
    requirements = f.read().splitlines()


setuptools.setup(
    name="py-draughts",
    version=__version__,
    author="Michał Skibiński",
    author_email="mskibinski109@gmail.com",
    description=__doc__.replace("\n", " ").strip(),
    long_description=long_description,
    # rst
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    package_data={"draughts": ["static/js/*", "static/css/*", "templates/*"]},
    install_requires=requirements,
    license="GPL-3.0+",
    keywords=" draughts, checkers, AI mini-max, game, board",
    url="https://github.com/michalskibinski109/draughts",
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
        "Documentation": "https://michalskibinski109.github.io/draughts/index.html",
    },
    python_requires=">=3.8",
)

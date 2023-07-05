import setuptools
from checkers.__init__ import __doc__
import os


def read_description():
    """
    Reads the description from README.rst and substitutes mentions of the
    latest version with a concrete version number.
    """
    with open("readme.md", encoding="utf-8") as f:
        description = f.read()
    return description
setuptools.setup(
    name="fast-checkers",
    version="0.0.3",
    author="Michał Skibiński",
    author_email="mskibinski109@gmail.com",
    files_to_include=["checkers"],
    description=__doc__.replace("\n", " ").strip(),
    long_description=read_description(),
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    url="https://github.com/michalskibinski109/checkers",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)

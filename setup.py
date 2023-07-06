import setuptools
from checkers.__init__ import __doc__


from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setuptools.setup(
    name="fast-checkers",
    version="0.0.5",
    author="Michał Skibiński",
    author_email="mskibinski109@gmail.com",
    files_to_include=["checkers"],
    description=__doc__.replace("\n", " ").strip(),
    long_description=long_description,
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

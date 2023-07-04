import setuptools


setuptools.setup(
    name="fast-checkers",
    version="0.0.2",
    author="Michał Skibiński",
    author_email="mskibinski109@gmail.com",
    files_to_include=["checkers"],
    long_description="Modern checkers library with fast move generation. Still under development.",
    packages=setuptools.find_packages(),
    url="https://github.com/michalskibinski109/checkers",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)

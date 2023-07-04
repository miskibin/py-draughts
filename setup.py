import setuptools


setuptools.setup(
    name="fast-checkers",
    version="0.0.1",
    author="Michał Skibiński",
    author_email="mskibinski109@gmail.com",
    files_to_include=["checkers"],
    long_description="Modern checkers library with fast move generation. Still in development.",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)

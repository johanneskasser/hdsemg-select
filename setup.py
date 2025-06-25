#!/usr/bin/env python
import os
import re
from pathlib import Path

from setuptools import setup, find_packages

version = os.getenv("PACKAGE_VERSION", "0.0.1")

if not re.match(r"^\d+\.", version):
    print("ERROR: PACKAGE_VERSION must be in format X.Y.Z. Setting to 0.0.1.")
    version = "0.0.1"

this_dir = Path(__file__).parent
long_description = (this_dir / "README.md").read_text(encoding="utf-8")


setup(
    name="hdsemg-select",
    version=version,
    description="hdsemg-select package",
    author="Johannes Kasser",
    author_email="johanneskasser@outlook.de",
    url="https://github.com/johanneskasser/hdsemg-select",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_data={
        "hdsemg_select": ["*"]
    },
    install_requires=[
        "PyQt5>=5.15.0",
        "pyqt5-tools>=5.15.0; sys_platform == 'win32'",
        "matplotlib>=3.4.0",
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "pyinstaller>=6.11.0",
        "requests>=2.30.0",
        "hdsemg-shared>=0.11.1",
        "pefile>=2023.2.7; sys_platform != 'win32'",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
             "hdsemg-select=hdsemg_select.main:main",
        ],
    },
)

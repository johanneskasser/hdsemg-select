#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="hdsemg-select",
    version="0.1.0",
    description="hdsemg-select package",
    author="Your Name",
    author_email="you@example.com",
    url="https://github.com/johanneskasser/hdsemg-select",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "PyQt5>=5.15.0",
        "pyqt5-tools>=5.15.0; sys_platform == 'win32'",
        "matplotlib>=3.4.0",
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "pyinstaller>=6.11.0",
        "requests>=2.30.0",
        "hdsemg-shared>=0.10.6",
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

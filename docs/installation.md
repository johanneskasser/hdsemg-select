# Installation Guide

This guide will walk you through the process of installing and setting up hdsemg-select on your system.

## Prerequisites

Before installing hdsemg-select, ensure you have:
- Python 3.8 or higher installed
- Git installed on your system
- Administrator access (for virtual environment creation)

## Installation

> There are several ways to install hdsemg-select:

### 1. Installation via PyPI

The package can be installed directly from PyPI:
```bash
pip install hdsemg-select
```

### 2. Installation from Source

Follow these steps to install the project from source:

1. Clone the repository:
   ```bash
   git clone https://github.com/johanneskasser/hdsemg-select.git
   cd hdsemg-select
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Compile the Resource File

Navigate to the source directory and compile the resource file:
```bash
cd ./src/hdsemg_select
pyrcc5 resources.qrc -o resources_rc.py
```

4. Start the Application

Run the main Python script to start the application:
```bash
python main.py
```

### 3. Precompiled Versions (Windows & macOS)

Precompiled .exe and macOS programs are available for download under the [Releases](https://github.com/johanneskasser/hdsemg-select/releases). Download the appropriate file and follow the instructions to run it.

## Troubleshooting

### Common Issues

1. **Virtual Environment Creation Fails**
   - Ensure you're running the command prompt as administrator
   - Verify Python is correctly installed and in your system PATH

2. **Missing Dependencies**
   - Try reinstalling requirements: `pip install -r requirements.txt`
   - Check for any error messages during installation

3. **Resource Compilation Error**
   - Ensure PyQt5 is properly installed
   - Verify the `resources.qrc` file exists in the src directory

## System Compatibility

The application has been tested on:
- Windows 11
- Linux distributions

For platform-specific issues, please check our [GitHub issues page](https://github.com/johanneskasser/hdsemg-select/issues).

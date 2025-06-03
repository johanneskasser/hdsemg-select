# Installation Guide

This guide will walk you through the process of installing and setting up hdsemg-select on your system.

## Prerequisites

Before installing hdsemg-select, ensure you have:
- Python 3.8 or higher installed
- Git installed on your system
- Administrator access (for virtual environment creation)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/johanneskasser/hdsemg-select.git
cd hdsemg-select
```

### 2. Set Up Virtual Environment

You have two options for setting up your development environment:

#### Option 1: Using Python venv
```bash
# Run as administrator
python -m venv venv
source venv/bin/activate  # On Windows use venv\Scripts\activate
pip install -r requirements.txt
```

#### Option 2: Using Conda
```bash
conda env create -f environment.yml
conda activate hdsemg-select
```

### 3. Compile Resource File

Navigate to the source directory and compile the resource file:
```bash
cd ./src
pyrcc5 resources.qrc -o resources_rc.py
```

### 4. Launch the Application

Run the main Python script to start the application:
```bash
python main.py
```

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

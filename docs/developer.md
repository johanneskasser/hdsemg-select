# Developer Guide

This guide provides information for developers who want to contribute to or modify the hdsemg-select application.

## Project Structure

```
src/
├── __init__.py
├── main.py                 # Application entry point
├── version.py             # Version information
├── _log/                  # Logging configuration
├── config/               # Application configuration
├── controller/           # Application controllers
├── helper/              # Utility functions
├── select_logic/        # Core selection algorithms
├── settings/           # Settings management
├── state/              # Application state management
└── ui/                 # User interface components
```

## Development Setup

1. Fork the repository
2. Set up your development environment following the [Installation Guide](installation.md)
3. Install additional development dependencies:
   ```bash
   pip install pytest pytest-cov pylint
   ```

## Coding Standards

- Follow PEP 8 style guide
- Write docstrings for all public methods
- Maintain type hints
- Keep methods focused and single-responsibility
- Write unit tests for new features

## Testing

### Running Tests
```bash
python -m pytest
```

### Test Coverage
```bash
python -m pytest --cov=src
```

## Building

### Resource Compilation
```bash
cd src
pyrcc5 resources.qrc -o resources_rc.py
```

### Creating Executables
- Windows:
  ```bash
  pyinstaller src/hdsemg_select-win.spec
  ```
- macOS:
  ```bash
  pyinstaller src/hdsemg_select-macos.spec
  ```

## Core Components

### Signal Processing
- Located in `select_logic/data_processing.py`
- Handles raw signal manipulation
- Implements filtering algorithms

### Artifact Detection
- Located in `select_logic/auto_flagger.py`
- ECG contamination detection
- Power line noise identification
- Custom artifact detection algorithms

### UI Components
- Based on PyQt5
- Custom widgets in `ui/widgets/`
- Plot components using pyqtgraph

## Contributing

### Pull Request Process
1. Create a feature branch
2. Implement changes
3. Add/update tests
4. Update documentation
5. Submit PR with description

### Version Control
- Use semantic versioning
- Update version.py
- Document changes in CHANGELOG.md

## Architecture

### Data Flow
1. File Loading → Grid Detection → Signal Processing
2. User Interface ←→ State Management
3. Selection Logic → Data Export

### State Management
- Centralized state in `state/state.py`
- Event-driven updates
- PyQt signals and slots

## Performance Considerations

### Large Dataset Handling
- Implement pagination
- Use memory-efficient data structures
- Consider chunked processing

### Optimization Tips
- Profile code using cProfile
- Optimize heavy computations
- Use NumPy for array operations

## Debugging

### Logging
- Configure in `_log/log_config.py`
- Use appropriate log levels
- Include context in log messages

### Common Issues
- Resource compilation errors
- Memory management
- Qt event loop issues

## Future Development

### Planned Features
- Additional file format support
- Enhanced artifact detection
- Performance optimizations
- Extended analysis tools

### Roadmap
1. Improve automatic detection
2. Add batch processing
3. Implement additional exports
4. Enhance visualization options

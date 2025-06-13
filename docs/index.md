<div align="center">
<br>
  <img src="img/favicon.ico" alt="App Icon" width="100" height="100"><br>
    <h2 align="center">🧼 hdsemg-select 🧼</h2>
    <h3 align="center">HDsEMG data cleaning tool</h3>
</div>

Welcome to the documentation for hdsemg-select, a sophisticated graphical user interface (GUI) application designed for selecting and analyzing HDsEMG channels from `.mat` files. This tool helps identify and exclude faulty channels (e.g., due to electrode misplacement or corrosion) and automatically flag potential artifacts like ECG contamination, power line noise (50/60Hz), or general signal anomalies.

[![GitHub Repo](https://img.shields.io/badge/GitHub-hdsemg--select-blue?logo=github&style=flat-square)](https://github.com/johanneskasser/hdsemg-select)

## Key Features

- ✅ Support for multiple file formats (`.mat`, `.otb+`, `.otb4`)
- 🧠 Intelligent grid detection and configuration
- 🖼 Comprehensive visualization tools
- ⚡️ Advanced artifact detection
- 💾 Structured data export
- 🔍 Detailed signal analysis capabilities

## Quick Navigation

- [Installation Guide](installation.md): Step-by-step instructions for setting up hdsemg-select
- [Getting Started](usage/getting_started.md): Learn how to get started with the application. The documentation will guide you through the first steps of using the hdsemg-select application to inspect and clean your high-density surface EMG (HD-sEMG) data.
- [Developer Guide](developer.md): Information for contributors and developers

## Core Functionality

### Signal Visualization
- Grid-based electrode visualization
- Time-domain and frequency spectrum analysis
- Multi-channel overview with pagination
- Reference signal overlay capabilities

### Channel Management
- Manual and automatic channel selection
- Amplitude-based selection with configurable thresholds
- Custom label management
- Comprehensive artifact flagging system

### Data Processing
- Automatic artifact detection
    - ECG contamination identification
    - Power line noise detection (50/60Hz)
    - General signal anomaly detection
- Signal view options (MP, SD, DD)
- Action potential propagation analysis

### Data Export
- Structured JSON export with channel metadata
- Automated cleaned `.mat` file generation
- Comprehensive channel labeling system

## Requirements

- Python 3.8+
- See `requirements.txt` for detailed dependencies
- Compatible with Linux and Windows 11

## Related Tools

- [hdsemg-pipe App 🧼](https://github.com/johanneskasser/hdsemg-pipe.git)
- [hdsemg-shared 📦](https://github.com/johanneskasser/hdsemg-shared.git)
- [openhdemg 🧬](https://github.com/GiacomoValliPhD/openhdemg)

## Contributing

Contributions are welcome! If you'd like to improve hdsemg-select, please take a look at our [Contributing Guide](contributing.md) for details on how to get started.

> Visit our [GitHub repository](https://github.com/johanneskasser/hdsemg-select) to get started.

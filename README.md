<div align="center">
<br>
  <img src="src/hdsemg_select/resources/icon.png" alt="App Icon" width="100" height="100"><br>
    <h2 align="center">🧼 hdsemg-select 🧼</h2>
    <h3 align="center">HDsEMG data cleaning tool</h3>
</div>

A graphical user interface (GUI) application for selecting and analyzing HDsEMG channels from `.mat` files. This tool
helps identify and exclude faulty channels and automatically flag potential artifacts like ECG contamination, power line noise (50/60Hz), or general signal anomalies.

📚 **[View the full documentation](https://johanneskasser.github.io/hdsemg-select/)**

## Key Features

- ✅ Support for multiple file formats (`.mat`, `.otb+`, `.otb4`)
- 🧠 Intelligent grid detection and configuration
- 🖼 Comprehensive visualization tools
- ⚡️ Advanced artifact detection
- 💾 Structured data export
- 🔍 Detailed signal analysis capabilities

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/johanneskasser/hdsemg-select.git
   cd hdsemg_select
   ```

2. **Create virtual environment (as admin):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python src/main.py
   ```

📖 For detailed instructions, visit our [Installation Guide](https://johanneskasser.github.io/hdsemg-select/installation).

## Documentation

- 📥 [Installation Guide](https://johanneskasser.github.io/hdsemg-select/installation)
- 📖 [Usage Guide](https://johanneskasser.github.io/hdsemg-select/usage)
- 🛠 [Developer Guide](https://johanneskasser.github.io/hdsemg-select/developer)

## Screenshots

<div align="center">
  <img src="docs/img/dashboard.png" alt="Dashboard" width="100%">
  <img src="docs/img/signal_overview_plot/signal_overview_plot.png" alt="Signal Overview Plot" width="100%">
</div>

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies
- Tested on Linux and Windows 11

## Related Tools

- [hdsemg-pipe App 🧼](https://github.com/johanneskasser/hdsemg-pipe.git)
- [openhdemg 🧬](https://github.com/GiacomoValliPhD/openhdemg)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

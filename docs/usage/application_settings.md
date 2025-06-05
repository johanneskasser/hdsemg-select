## Application Settings

This section describes how to configure application settings in the hdsemg-select application, including automatic channel flagging settings and custom flags.

### Accessing Application Settings
1. Open the **"File"** menu in the top navigation bar.
2. Select **"Settings..."** to open the settings dialog.
3. The settings dialog opens

![Settings Dialog](../img/settings/settings_dialog.png)

### Logging Settings

The first tab allows you to configure the logging settings for the application and shows the current log level:
- **Log Level**: Choose the level of detail for logging messages. Options include:
  - `DEBUG`: Detailed information, useful for debugging.
  - `INFO`: General information about application operations.
  - `WARNING`: Indications of potential issues.
  - `ERROR`: Error messages indicating problems that need attention.
  - `CRITICAL`: Severe errors that may prevent the application from functioning.

### Automatic Channel Flagging Settings

The second tab allows you to configure the automatic channel flagging behavior, which helps detect and label noisy or artifact-prone channels.

- **Noise Frequency Threshold:** Defines how strong a frequency peak (e.g. at 50/60 Hz) must be relative to the background to trigger a noise flag.
- **Artifact Variance Threshold:** Channels with a variance above this threshold are flagged as containing artifacts.
- **Noise Frequency Band (Hz):** Sets the width of the frequency band around each target (e.g. ±1.2 Hz around 50 Hz) to search for noise peaks.

You can also enable or disable checks for:
- **50 Hz Noise**
- **60 Hz Noise**

These settings directly control how the automatic flagging algorithm evaluates each channel.

![Automatic Channel Flagging Settings](../img/settings/automatic_channel_flag_settings.png)

### Custom Flags

The third tab allows you to manage custom flags that can be applied to channels. Custom flags are useful for specific use cases or personal preferences.

If you want to add a custom flag, follow these steps:

1. Navigate to the **"Custom Flags"** tab in the settings dialog.
2. Click the **"Add"** button to add a new custom flag.
3. Enter a name and a color for the custom flag in the input field.
4. Click **"Create"** to apply the changes.
5. The new custom flag will now appear in the dropdown menu when labeling channels. 
<br> **Note:** You can also delete custom flags by selecting them and clicking the **"Delete"** button.
6. Press **OK** to save your changes and close the settings dialog.

Now you can use the custom flag in the channel labeling dialog to mark channels with specific characteristics or issues.

---
### Settings: Under the Hood

The settings are stored in a JSON file located in the application data directory. The file is named `settings.json` and contains all the configuration options, including logging level, automatic channel flagging settings, and custom flags.
So, if you want to use your own settings across multiple installations, you can copy the settings file to the same location on the other machine. The application will automatically load the settings from this file when it starts. This also allows you to reset your application to the default settings by deleting or renaming the `config.json` file, which will cause the application to create a new one with default values.
The Settings File is located in the following directory:
- `<PATH_TO_YOUR_HDSEMG_SHARED_INSTALLATION>/config/config.json`

#### Settings File Structure

The File is very basic and structured as follows:

```json
{
    "LOG_LEVEL": "DEBUG",
    "AUTO_FLAGGER_NOISE_FREQ_THRESHOLD": 2.4,
    "AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD": 5e-09,
    "AUTO_FLAGGER_NOISE_FREQ_BAND_HZ": 1.2,
    "AUTO_FLAGGER_CHECK_50HZ": true,
    "AUTO_FLAGGER_CHECK_60HZ": true,
    "CUSTOM_FLAG_LAST_ID": 2,
    "CUSTOM_FLAGS": [
        {
            "id": "0b8a7003-e911-4163-9305-efb00593557e",
            "name": "test",
            "color": "#55aa00"
        }
    ]
}
```

<div align="center">

<img src="windows/phonemic.png" alt="PhoneMic Logo" width="140"/>

# PhoneMic

**Use your Android phone as a microphone on Windows — over USB**

[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?logo=windows)](https://github.com/xeodeo/PhoneMic/releases)
[![Android](https://img.shields.io/badge/Android-5.0%2B-3DDC84?logo=android&logoColor=white)](https://github.com/xeodeo/PhoneMic/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Release](https://img.shields.io/github/v/release/xeodeo/PhoneMic?color=success)](https://github.com/xeodeo/PhoneMic/releases/latest)

[**Download**](https://github.com/xeodeo/PhoneMic/releases/latest) · [How it works](#how-it-works) · [Quick start](#quick-start) · [FAQ](#faq)

</div>

---

## What is PhoneMic?

PhoneMic turns your Android phone into a high-quality USB microphone for Windows — no Wi-Fi, no latency spikes, no proprietary drivers. It streams raw PCM audio over a USB cable through ADB, then feeds it into any virtual audio device (VB-Cable, VoiceMeeter, VAC, etc.) so apps like **Discord, Zoom, OBS, Teams** see it as a regular microphone.

<div align="center">

```
📱 Android Phone                      💻 Windows PC
┌─────────────────────┐               ┌──────────────────────────────────┐
│  PhoneMic App       │               │  PhoneMic Client                 │
│  ─────────────────  │  USB Cable    │  ──────────────────────────────  │
│  AudioRecord API    │──────────────▶│  ADB Port Forward (tcp:7777)     │
│  16000 Hz · PCM16   │  (ADB)        │  ↓                               │
│  TCP Server :7777   │               │  sounddevice output stream       │
└─────────────────────┘               │  ↓                               │
                                      │  Virtual Audio Device (VB-Cable) │
                                      │  ↓                               │
                                      │  🎙️ Discord / Zoom / OBS / etc. │
                                      └──────────────────────────────────┘
```

</div>

---

## Features

- **USB only** — stable, low-latency, no Wi-Fi dependency
- **WiFi mode** — also supports wireless connection when USB isn't available
- **No kernel drivers** — works with any existing virtual audio device
- **Volume control** — adjustable on both the phone and the PC
- **Mute button** — on the phone and in the Windows app
- **System tray** — minimize to tray, runs in background
- **Bundled ADB** — no need to install Android SDK separately
- **Installer includes VB-Cable** — everything in one setup

---

## Quick Start

### Option A — Windows Installer (recommended)

1. [**Download PhoneMic_Setup.exe**](https://github.com/xeodeo/PhoneMic/releases/latest) and run it
2. It installs the Windows client, ADB, and optionally VB-Cable
3. Follow the steps below from step 2

### Option B — Manual / from source

```bash
pip install -r windows/requirements.txt
python windows/phonemic_client.py
```

---

## Step-by-step Usage

**1. Prepare your phone**

- Go to **Settings → About phone** → tap *Build number* 7 times to enable Developer Options
- Go to **Settings → Developer options** → enable **USB debugging**
- Connect your phone to the PC with a USB cable and **allow** the ADB authorization prompt

**2. Install the Android app**

- Build with Android Studio (`Run → Run 'app'`), or
- Sideload the APK from the [latest release](https://github.com/xeodeo/PhoneMic/releases/latest)

**3. Start streaming on the phone**

- Open **PhoneMic** on the phone
- Tap **Start** — the status turns yellow (waiting for client)

**4. Connect from Windows**

- Open the PhoneMic Windows client
- Select your virtual audio device from the dropdown (e.g. `CABLE Input (VB-Audio Virtual Cable)`)
- Press **Connect** — the phone status turns green and audio starts flowing

**5. Set the microphone in your app**

- In Discord, Zoom, OBS, etc., select **CABLE Output (VB-Audio Virtual Cable)** as your microphone input

---

## Audio Specs

| Parameter   | Value                  |
|-------------|------------------------|
| Sample rate | 16,000 Hz              |
| Channels    | 1 (mono)               |
| Bit depth   | PCM 16-bit signed LE   |
| Transport   | Raw TCP (no framing)   |
| Port        | 7777                   |
| Chunk size  | 4096 bytes             |

---

## Requirements

### Android
- Android 5.0 (Lollipop) or later
- USB debugging enabled

### Windows
- Windows 10 or later
- A virtual audio device: [VB-Cable](https://vb-audio.com/Cable/) *(free)*, VoiceMeeter, or similar — the installer includes VB-Cable automatically
- ADB — bundled with the installer. To install manually: download [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) and extract `adb.exe` anywhere (or add it to your PATH)

---

## vs. WoMic

| | WoMic | PhoneMic |
|---|---|---|
| Windows driver | Custom kernel driver (`.sys`) | Any virtual audio device |
| Protocol | Proprietary | Raw TCP PCM |
| Source code | Closed | Open |
| USB + WiFi | Yes | Yes |
| Installer | Yes | Yes |
| Customizable | No | Yes |

---

## Building from Source

### Android
```bash
cd android
./gradlew assembleDebug       # build APK
./gradlew installDebug        # build + install to connected device
```

### Windows executable
```bash
cd windows
build_exe.bat                 # produces dist/PhoneMic/
```

### Windows installer (requires [Inno Setup 6](https://jrsoftware.org/isinfo.php))
```
Open installer/phonemic_setup.iss in Inno Setup and click Compile
Output: installer/Output/PhoneMic_Setup.exe
```

---

## FAQ

**Q: The phone status stays yellow after connecting**
A: Make sure USB debugging is enabled and the ADB authorization was accepted on the phone. Try running `adb devices` in a terminal — your device should be listed as `device`. If it says `unauthorized`, unplug and replug, then accept the prompt on the phone.

> **Install ADB manually:** Download [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) → extract → add the folder to your PATH, or just drop `adb.exe` next to `phonemic_client.py`.

**Q: No virtual audio devices appear in the dropdown**
A: Install [VB-Cable](https://vb-audio.com/Cable/) (free) — direct download at `https://vb-audio.com/Cable/`. The PhoneMic installer includes it as an optional component.

**Q: Audio is choppy or has static**
A: Try a different USB cable or port. Also make sure no other app is capturing the ADB forward on port 7777.

**Q: Can I use WiFi instead of USB?**
A: Yes. In the phone app, go to the menu and switch to **WiFi mode**. Enter your phone's IP in the Windows client before connecting.

---

## License

MIT — see [LICENSE](LICENSE)

---

<div align="center">

Made with ♥ · [Report an issue](https://github.com/xeodeo/PhoneMic/issues)

</div>

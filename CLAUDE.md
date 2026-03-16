# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

PhoneMic streams audio from an Android phone's microphone to Windows via USB ADB (Android Debug Bridge). The Android app acts as a TCP server; the Windows Python client connects through ADB port forwarding and outputs audio to a virtual audio device (VB-Cable, VoiceMeeter, etc.).

## Project Structure

- `android/` — Android Studio project (Kotlin); builds the phone-side TCP audio server
- `windows/` — Python client with Tkinter GUI; runs on the PC

## Commands

### Android
Build and install via Android Studio, or:
```bash
cd android
./gradlew assembleDebug          # build APK
./gradlew installDebug           # build + install to connected device
```

### Windows
```bash
# First run (installs dependencies)
windows\instalar_y_ejecutar.bat

# Subsequent runs
windows\ejecutar.bat

# Manual
pip install -r windows/requirements.txt
python windows/phonemic_client.py
```

## Architecture

**Audio pipeline:**
```
Phone mic → AudioRecord (16000 Hz, PCM 16-bit mono) → TCP server (port 7777)
    → ADB port forward (usb) → Windows TCP client → PyAudio → virtual audio device
```

**Android (`MainActivity.kt`):** Single-activity app. TCP server on port 7777 runs on a background thread. `AudioRecord` captures raw PCM and writes bytes directly to the socket. Requires `RECORD_AUDIO` and `INTERNET` permissions.

**Windows (`phonemic_client.py`):** `PhoneMicClient` handles ADB forwarding (via subprocess to `adb.exe`), TCP connection to `localhost:7777`, and writing received bytes to a PyAudio output stream. The `App` class is a Tkinter GUI that auto-detects virtual audio devices by name (keywords: `cable`, `virtual`, `vb-audio`, `voicemeeter`, `vac`).

**Protocol:** Raw TCP — no framing or headers. 4096-byte chunks. ADB forward must be active before connecting.

**Threading:** GUI on main thread; audio receive loop is a daemon thread. Android streams on socket I/O thread.

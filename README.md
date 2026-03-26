# PhoneMic

Usa el micrófono de tu celular Android como micrófono en Windows, conectado por **cable USB** o por **WiFi** (red local).

---

## ¿Cómo funciona?

```
[Celular Android]  ──USB o WiFi──▶  [Windows]  ──▶  [Dispositivo virtual]
  Micrófono                          PhoneMic.exe       VB-Cable / VoiceMeeter
  TCP Server :7777                   Recibe audio        Aparece como micrófono
```

La app Android captura audio del micrófono (PCM 16-bit) y lo transmite por TCP al cliente Windows, que lo reproduce en un dispositivo de audio virtual. Desde ahí, cualquier aplicación (Discord, Zoom, OBS, etc.) puede usarlo como micrófono.

---

## Descargas necesarias

| Componente | URL | Para qué sirve |
|-----------|-----|----------------|
| **VB-Cable** | https://vb-audio.com/Cable/ | Crea un micrófono virtual en Windows (necesario para Discord, Zoom, OBS) |
| **ADB platform-tools** | https://dl.google.com/android/repository/platform-tools-latest-windows.zip | Herramienta de conexión USB entre Android y Windows |
| **Driver USB Android (Google)** | https://developer.android.com/studio/run/win-usb | Driver para que Windows reconozca el celular por USB |

> **El instalador `PhoneMic_Setup.exe` ya incluye ADB y VB-Cable.** Solo necesitas descargar el driver USB si Windows no reconoce el celular.

---

## Instalación rápida (recomendada)

1. Descarga y ejecuta **`PhoneMic_Setup.exe`**
2. El instalador incluye:
   - PhoneMic para Windows
   - ADB (Android Debug Bridge)
   - VB-Cable (dispositivo virtual de audio) — opcional, pero recomendado
3. Instala la app en el celular (conectado por USB con Depuración USB activa):
   ```
   adb install PhoneMic.apk
   ```
   *(El APK queda en la carpeta de instalación: `C:\Program Files\PhoneMic\`)*

---

## Uso

### Conexión por USB (recomendada)

1. Conecta el celular al PC con cable USB
2. En el celular: **Ajustes → Opciones de desarrollador → Depuración USB** (activar)
3. Si aparece un aviso en el celular, toca **Permitir**
4. Abre **PhoneMic** en el celular y toca **Iniciar**
5. Abre **PhoneMic** en Windows
6. Selecciona el modo **USB** y el dispositivo de audio
7. Presiona **Conectar**

> Si Windows no detecta el celular, instala el **Driver USB Android**: https://developer.android.com/studio/run/win-usb

### Conexión por WiFi

1. Celular y PC deben estar en la **misma red WiFi**
2. Abre **PhoneMic** en el celular, ve a **Configuración → WiFi** y anota la IP que aparece
3. En Windows, selecciona modo **WiFi** e ingresa la IP
4. Presiona **Conectar**

---

## Dispositivo virtual de audio

Para que otras apps reconozcan el audio como micrófono se necesita un dispositivo virtual:

| Dispositivo | Descarga | Cómo usarlo |
|-------------|----------|-------------|
| **VB-Cable** (incluido en el instalador) | https://vb-audio.com/Cable/ | Selecciona `CABLE Input` en PhoneMic Windows; en Discord/Zoom elige `CABLE Output` como micrófono |
| **VoiceMeeter** | https://vb-audio.com/Voicemeeter/ | Selecciona la entrada de VoiceMeeter en PhoneMic |

---

## Opciones de audio

| Opción | Descripción |
|--------|-------------|
| Calidad estándar | 16 000 Hz — menor latencia, menos ancho de banda |
| Alta calidad | 44 100 Hz — mejor calidad, algo más de latencia |
| Noise Gate | Silencia el audio por debajo de un umbral configurable |
| Silenciar | Silencia el micrófono sin desconectar |

---

## Formato técnico

| Parámetro | Valor |
|-----------|-------|
| Sample rate | 16 000 Hz (estándar) / 44 100 Hz (alta calidad) |
| Canales | 1 (mono) |
| Formato | PCM 16-bit signed little-endian |
| Protocolo | TCP raw — cabecera `PHONEMIC:SR:CH\n` + PCM |
| Puerto | 7777 |

---

## Compilar desde el código fuente

### App Android
```bash
cd android
./gradlew assembleDebug          # genera APK en android/app/build/outputs/apk/debug/
./gradlew installDebug           # compila e instala directamente en el celular
```

### Cliente Windows (EXE)
```bash
cd windows
build_exe.bat                    # genera windows/dist/PhoneMic/PhoneMic.exe
```

### Instalador

**Requisitos previos:**
- **Inno Setup 6** — https://jrsoftware.org/isdl.php
- **ADB platform-tools** — https://dl.google.com/android/repository/platform-tools-latest-windows.zip
  *(extrae en `installer/adb_files/platform-tools/`)*
- **VB-Cable** — https://vb-audio.com/Cable/
  *(copia los archivos del driver en `installer/vbcable/`)*

**Pasos:**
1. Ejecuta `windows\build_exe.bat`
2. Abre `installer\phonemic_setup.iss` en **Inno Setup 6**
3. Compila con `Ctrl+F9` → genera `installer\Output\PhoneMic_Setup.exe`

---

## Estructura del proyecto

```
PhoneMic/
├── android/                    App Android (Kotlin)
│   └── app/src/main/java/com/phonemic/app/
│       ├── MainActivity.kt     UI y control del servicio
│       └── MicService.kt       Foreground service — captura y transmite audio
├── windows/                    Cliente Windows (Python + PySide6)
│   ├── main.py                 Punto de entrada
│   ├── phonemic/
│   │   ├── ui/
│   │   │   ├── app.py          Ventana principal (QMainWindow)
│   │   │   └── widgets.py      MicSphere (widget personalizado)
│   │   ├── audio/
│   │   │   ├── client.py       Conexión ADB/WiFi + streaming de audio
│   │   │   └── processing.py   Volumen y noise gate
│   │   └── constants.py        Puerto, chunk size, sample rates
│   ├── build_exe.bat           Script de compilación con PyInstaller
│   └── requirements.txt        Dependencias Python
└── installer/
    ├── phonemic_setup.iss      Script Inno Setup 6
    ├── adb_files/              ADB platform-tools para Windows
    └── vbcable/                Driver VB-Cable
```

---

## Requisitos

**Android:** 6.0 (API 23) o superior

**Windows:** Windows 10/11 (64-bit)

**Para compilar el cliente Windows:**
- Python 3.8+
- `pip install -r windows/requirements.txt`
- PyInstaller (incluido en `build_exe.bat`)

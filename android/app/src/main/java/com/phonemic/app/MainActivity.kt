package com.phonemic.app

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.PopupMenu
import android.widget.SeekBar
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.net.Inet4Address
import java.net.NetworkInterface

class MainActivity : AppCompatActivity() {

    private val COLOR_IDLE    = "#4f545c"
    private val COLOR_WAITING = "#f0a500"   // amarillo — servidor activo, sin cliente
    private val COLOR_ACTIVE  = "#23a55a"   // verde — cliente conectado y transmitiendo
    private val COLOR_MUTED   = "#f23f43"
    private val COLOR_BLURPLE = "#5865f2"

    private val PREFS_NAME        = "phonemic"
    private val PREF_TRANSPORT    = "transport"
    private val PREF_HIGH_QUALITY = "high_quality"

    private lateinit var btnToggle:  Button
    private lateinit var btnMute:    Button
    private lateinit var tvStatus:   TextView
    private lateinit var tvVolume:   TextView
    private lateinit var micCircle:  FrameLayout
    private lateinit var ivMic:      ImageView
    private lateinit var seekVolume: SeekBar
    private lateinit var tvWifiIp:   TextView
    private lateinit var btnMenu:    TextView
    private lateinit var tvBadge:    TextView
    private lateinit var rowUsb:     LinearLayout
    private lateinit var rowWifi:    LinearLayout

    // ── Status receiver ───────────────────────────────────────────────────────

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val msg       = intent.getStringExtra(MicService.EXTRA_STATUS_MSG) ?: return
            val muted     = intent.getBooleanExtra(MicService.EXTRA_IS_MUTED,     false)
            val streaming = intent.getBooleanExtra(MicService.EXTRA_IS_STREAMING, false)
            val connected = intent.getBooleanExtra(MicService.EXTRA_IS_CONNECTED, false)

            val color = when {
                !streaming -> COLOR_IDLE
                muted      -> COLOR_MUTED
                connected  -> COLOR_ACTIVE
                else       -> COLOR_WAITING   // streaming pero sin cliente aún
            }
            updateStatus(msg, color)
            setCircleColor(color)
            syncUI(streaming, muted)
        }
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        btnToggle  = findViewById(R.id.btnToggle)
        btnMute    = findViewById(R.id.btnMute)
        tvStatus   = findViewById(R.id.tvStatus)
        tvVolume   = findViewById(R.id.tvVolume)
        micCircle  = findViewById(R.id.micCircle)
        ivMic      = findViewById(R.id.ivMic)
        seekVolume = findViewById(R.id.seekVolume)
        tvBadge    = findViewById(R.id.tvBadge)
        tvWifiIp   = findViewById(R.id.tvWifiIp)
        btnMenu    = findViewById(R.id.btnMenu)
        rowUsb     = findViewById(R.id.rowUsb)
        rowWifi    = findViewById(R.id.rowWifi)

        tvWifiIp.text = getWifiIpAddress()
        updateTransportCard(getTransport())

        // 3-dot menu
        btnMenu.setOnClickListener { view ->
            val popup = PopupMenu(this, view)
            popup.menuInflater.inflate(R.menu.main_menu, popup.menu)
            popup.setOnMenuItemClickListener { item ->
                when (item.itemId) {
                    R.id.menuSettings -> showSettingsDialog()
                    R.id.menuAbout    -> showAboutDialog()
                }
                true
            }
            popup.show()
        }

        btnToggle.setOnClickListener {
            if (MicService.isRunning) stopMicService() else startStreaming()
        }

        btnMute.setOnClickListener {
            sendServiceAction(MicService.ACTION_TOGGLE_MUTE)
        }

        seekVolume.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(bar: SeekBar, progress: Int, fromUser: Boolean) {
                tvVolume.text = "$progress%"
                if (fromUser) sendVolumeToService(progress / 100f)
            }
            override fun onStartTrackingTouch(bar: SeekBar) {}
            override fun onStopTrackingTouch(bar: SeekBar) {}
        })

        syncUI(MicService.isRunning, MicService.isMuted)
        setCircleColor(when {
            !MicService.isRunning  -> COLOR_IDLE
            MicService.isMuted     -> COLOR_MUTED
            MicService.isConnected -> COLOR_ACTIVE
            MicService.isRunning   -> COLOR_WAITING
            else                   -> COLOR_IDLE
        })
        if (MicService.isRunning) seekVolume.progress = (MicService.volumeLevel * 100).toInt()

        checkPermissions()
    }

    override fun onResume() {
        super.onResume()
        val filter = IntentFilter(MicService.ACTION_STATUS_UPDATE)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(statusReceiver, filter)
        }
        // Sincronizar UI con el estado real del servicio al volver a la pantalla
        syncUI(MicService.isRunning, MicService.isMuted)
        val color = when {
            !MicService.isRunning  -> COLOR_IDLE
            MicService.isMuted     -> COLOR_MUTED
            MicService.isConnected -> COLOR_ACTIVE
            else                   -> COLOR_WAITING
        }
        setCircleColor(color)
        tvStatus.text = when {
            !MicService.isRunning  -> "Detenido"
            MicService.isConnected -> if (MicService.isMuted) "Silenciado" else "Transmitiendo audio"
            else                   -> "Esperando conexión..."
        }
        tvStatus.setTextColor(Color.parseColor(color))
        if (MicService.isRunning) seekVolume.progress = (MicService.volumeLevel * 100).toInt()
    }

    override fun onPause() {
        super.onPause()
        try { unregisterReceiver(statusReceiver) } catch (_: Exception) {}
    }

    // ── Permissions ───────────────────────────────────────────────────────────

    private fun checkPermissions() {
        val needed = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) needed += Manifest.permission.RECORD_AUDIO

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) needed += Manifest.permission.POST_NOTIFICATIONS

        if (needed.isNotEmpty())
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), 1)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 1 && grantResults.any { it != PackageManager.PERMISSION_GRANTED }) {
            updateStatus("Permiso requerido para funcionar", COLOR_MUTED)
        }
    }

    // ── Service control ───────────────────────────────────────────────────────

    private fun getTransport(): String =
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .getString(PREF_TRANSPORT, "usb") ?: "usb"

    private fun getHighQuality(): Boolean =
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .getBoolean(PREF_HIGH_QUALITY, false)

    private fun startStreaming() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            updateStatus("Se necesita permiso de micrófono", COLOR_MUTED)
            checkPermissions()
            return
        }
        val intent = Intent(this, MicService::class.java).apply {
            putExtra(MicService.EXTRA_TRANSPORT, getTransport())
            putExtra(MicService.EXTRA_HIGH_QUALITY, getHighQuality())
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        syncUI(streaming = true, muted = false)
        setCircleColor(COLOR_WAITING)
        updateStatus("Esperando conexión...", COLOR_WAITING)
    }

    private fun stopMicService() {
        sendServiceAction(MicService.ACTION_STOP)
        syncUI(streaming = false, muted = false)
        updateStatus("Detenido", COLOR_IDLE)
        setCircleColor(COLOR_IDLE)
    }

    private fun sendServiceAction(action: String) {
        startService(Intent(this, MicService::class.java).apply { this.action = action })
    }

    private fun sendVolumeToService(volume: Float) {
        MicService.volumeLevel = volume
        startService(Intent(this, MicService::class.java).apply {
            action = MicService.ACTION_SET_VOLUME
            putExtra(MicService.EXTRA_VOLUME, volume)
        })
    }

    // ── UI helpers ────────────────────────────────────────────────────────────

    private fun syncUI(streaming: Boolean, muted: Boolean) {
        btnToggle.text = if (streaming) "Detener" else "Iniciar"
        btnToggle.backgroundTintList = ColorStateList.valueOf(
            Color.parseColor(if (streaming) "#fa5252" else COLOR_BLURPLE)
        )
        btnMute.isEnabled = streaming
        btnMute.alpha = if (streaming) 1f else 0.5f
        btnMute.text = if (muted) "🔇  Activar micrófono" else "🎤  Silenciar micrófono"
        btnMute.backgroundTintList = ColorStateList.valueOf(
            Color.parseColor(if (muted) "#fa5252" else "#5865f2")
        )
        seekVolume.isEnabled = streaming
    }

    private fun setCircleColor(hex: String) {
        micCircle.backgroundTintList = ColorStateList.valueOf(Color.parseColor(hex))
        val iconAlpha = if (hex == COLOR_IDLE) 120 else 255
        ivMic.imageTintList = ColorStateList.valueOf(Color.argb(iconAlpha, 255, 255, 255))
        val (badgeText, badgeColor) = when (hex) {
            COLOR_ACTIVE  -> Pair("● CONECTADO",  "#23a55a")
            COLOR_MUTED   -> Pair("● SILENCIADO", "#f23f43")
            COLOR_WAITING -> Pair("● ESPERANDO",  "#f0a500")
            else          -> Pair("● INACTIVO",   "#4f545c")
        }
        tvBadge.text = badgeText
        tvBadge.backgroundTintList = ColorStateList.valueOf(Color.parseColor(badgeColor))
    }

    private fun updateStatus(msg: String, colorHex: String = COLOR_IDLE) {
        tvStatus.text = msg
        tvStatus.setTextColor(Color.parseColor(colorHex))
    }

    // ── Settings ──────────────────────────────────────────────────────────────

    private fun updateTransportCard(transport: String) {
        rowUsb.visibility  = if (transport == "usb")  View.VISIBLE else View.GONE
        rowWifi.visibility = if (transport == "wifi") View.VISIBLE else View.GONE
    }

    private fun showSettingsDialog() {
        val prefs       = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val current     = prefs.getString(PREF_TRANSPORT, "usb") ?: "usb"
        val currentHQ   = prefs.getBoolean(PREF_HIGH_QUALITY, false)
        val transportOptions = arrayOf("🔌  USB (ADB) — conecta por cable", "📶  WiFi (red local) — sin cable")
        val transportChecked = if (current == "usb") 0 else 1

        // Build a custom view with transport radio + high quality checkbox
        val dialogView = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(48, 16, 48, 8)
        }

        val tvTransport = android.widget.TextView(this).apply {
            text = "Modo de conexión"
            setTextColor(android.graphics.Color.parseColor("#b5bac1"))
            textSize = 13f
            setPadding(0, 16, 0, 8)
        }
        dialogView.addView(tvTransport)

        val rgTransport = android.widget.RadioGroup(this).apply {
            orientation = android.widget.RadioGroup.VERTICAL
        }
        transportOptions.forEachIndexed { i, label ->
            val rb = android.widget.RadioButton(this).apply {
                text = label
                id = i
                isChecked = (i == transportChecked)
                setTextColor(android.graphics.Color.parseColor("#f2f3f5"))
            }
            rgTransport.addView(rb)
        }
        dialogView.addView(rgTransport)

        val divider = android.view.View(this).apply {
            setBackgroundColor(android.graphics.Color.parseColor("#3a3d47"))
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, 1
            ).also { it.setMargins(0, 16, 0, 16) }
        }
        dialogView.addView(divider)

        val cbHighQuality = android.widget.CheckBox(this).apply {
            text = "Alta calidad (44 100 Hz)"
            isChecked = currentHQ
            setTextColor(android.graphics.Color.parseColor("#f2f3f5"))
        }
        dialogView.addView(cbHighQuality)

        AlertDialog.Builder(this, R.style.DarkDialog)
            .setTitle("Configuración")
            .setView(dialogView)
            .setPositiveButton("Guardar") { _, _ ->
                val selectedId = rgTransport.checkedRadioButtonId
                val transport = if (selectedId == 0) "usb" else "wifi"
                val hq = cbHighQuality.isChecked
                prefs.edit()
                    .putString(PREF_TRANSPORT, transport)
                    .putBoolean(PREF_HIGH_QUALITY, hq)
                    .apply()
                updateTransportCard(transport)
                if (MicService.isRunning) {
                    stopMicService()
                    btnToggle.postDelayed({ startStreaming() }, 400)
                }
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    // ── Misc ──────────────────────────────────────────────────────────────────

    private fun getWifiIpAddress(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                if (!iface.isLoopback && iface.isUp) {
                    val addrs = iface.inetAddresses
                    while (addrs.hasMoreElements()) {
                        val addr = addrs.nextElement()
                        if (!addr.isLoopbackAddress && addr is Inet4Address) {
                            return "${addr.hostAddress} : 7777"
                        }
                    }
                }
            }
        } catch (_: Exception) {}
        return "Sin conexión WiFi"
    }

    private fun showAboutDialog() {
        AlertDialog.Builder(this)
            .setTitle("PhoneMic")
            .setMessage("Versión 1.0\n\nUsa tu celular como micrófono vía USB (ADB) o WiFi (red local).\n\nPuerto: 7777")
            .setPositiveButton("OK", null)
            .show()
    }
}

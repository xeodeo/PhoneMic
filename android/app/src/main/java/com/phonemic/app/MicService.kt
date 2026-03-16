package com.phonemic.app

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean

class MicService : Service() {

    companion object {
        const val ACTION_STOP          = "com.phonemic.app.STOP"
        const val ACTION_TOGGLE_MUTE   = "com.phonemic.app.TOGGLE_MUTE"
        const val ACTION_SET_VOLUME    = "com.phonemic.app.SET_VOLUME"
        const val ACTION_STATUS_UPDATE = "com.phonemic.app.STATUS_UPDATE"

        const val EXTRA_STATUS_MSG   = "status_msg"
        const val EXTRA_IS_MUTED     = "is_muted"
        const val EXTRA_IS_STREAMING = "is_streaming"
        const val EXTRA_IS_CONNECTED = "is_connected"   // cliente activamente conectado
        const val EXTRA_VOLUME       = "volume"
        const val EXTRA_TRANSPORT    = "transport"

        const val CHANNEL_ID      = "phonemic_channel"
        const val NOTIFICATION_ID = 1

        @Volatile var isRunning    = false
        @Volatile var isMuted      = false
        @Volatile var isConnected  = false
        @Volatile var volumeLevel  = 1.0f
    }

    private val TAG          = "MicService"
    private val PORT         = 7777
    private val SAMPLE_RATE  = 16000
    private val CHAN_CONFIG  = AudioFormat.CHANNEL_IN_MONO
    private val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT

    private val isActive = AtomicBoolean(false)
    private var transport    = "usb"   // "usb" | "wifi"
    private var serverThread: Thread? = null
    private var serverSocket: ServerSocket? = null
    private var audioRecord:  AudioRecord? = null
    private var wakeLock:     PowerManager.WakeLock? = null

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                doStop()
                return START_NOT_STICKY
            }
            ACTION_TOGGLE_MUTE -> {
                isMuted = !isMuted
                updateNotification()
                broadcast(if (isMuted) "Silenciado" else "Transmitiendo audio")
                return START_STICKY
            }
            ACTION_SET_VOLUME -> {
                volumeLevel = intent.getFloatExtra(EXTRA_VOLUME, 1.0f)
                return START_STICKY
            }
        }

        if (!isActive.get()) {
            transport = intent?.getStringExtra(EXTRA_TRANSPORT) ?: "usb"
            isActive.set(true)
            isRunning   = true
            isConnected = false
            isMuted     = false
            acquireWakeLock()
            val notification = buildNotification("Esperando conexión...")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(
                    NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                )
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
            serverThread = Thread { runServer() }.also { it.start() }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        doStop()
    }

    // ── Core logic ────────────────────────────────────────────────────────────

    private fun doStop() {
        if (!isActive.getAndSet(false)) return   // ya detenido, evitar doble llamada
        isRunning   = false
        isConnected = false
        try { serverSocket?.close() }  catch (_: Exception) {}
        try { audioRecord?.stop() }    catch (_: Exception) {}
        try { audioRecord?.release() } catch (_: Exception) {}
        audioRecord = null
        releaseWakeLock()
        broadcast("Inactivo", streaming = false, connected = false)
        try { stopForeground(STOP_FOREGROUND_REMOVE) } catch (_: Exception) {}
        stopSelf()
    }

    private fun runServer() {
        try {
            // Bind solo a loopback en modo USB (solo ADB), a todas las interfaces en WiFi
            serverSocket = if (transport == "usb") {
                ServerSocket(PORT, 50, InetAddress.getByName("127.0.0.1"))
            } else {
                ServerSocket(PORT)
            }
            serverSocket!!.use { srv ->
                while (isActive.get()) {
                    isConnected = false
                    broadcast("Esperando conexión...")
                    updateNotification("Esperando conexión...")
                    try {
                        val client = srv.accept()
                        isConnected = true
                        broadcast("Transmitiendo audio", connected = true)
                        updateNotification(if (isMuted) "Silenciado" else "Transmitiendo audio")
                        streamAudio(client)
                    } catch (e: IOException) {
                        if (isActive.get()) Log.e(TAG, "Error cliente: ${e.message}")
                    }
                }
            }
        } catch (e: IOException) {
            if (isActive.get()) {
                Log.e(TAG, "Error servidor: ${e.message}")
                broadcast("Error: ${e.message}", streaming = false, connected = false)
            }
        }
    }

    private fun streamAudio(socket: Socket) {
        val minBuf  = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHAN_CONFIG, AUDIO_FORMAT)
        val bufSize = maxOf(minBuf, 4096)

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE, CHAN_CONFIG, AUDIO_FORMAT, bufSize
        )
        audioRecord!!.startRecording()

        val buffer = ByteArray(bufSize)
        socket.use { sock ->
            val out = sock.getOutputStream()
            while (isActive.get() && !sock.isClosed) {
                val read = audioRecord?.read(buffer, 0, bufSize) ?: -1
                if (read > 0) {
                    try {
                        out.write(processAudio(buffer, read), 0, read)
                        out.flush()
                    } catch (_: IOException) { break }
                }
            }
        }

        try { audioRecord?.stop() }    catch (_: Exception) {}
        try { audioRecord?.release() } catch (_: Exception) {}
        audioRecord = null
        isConnected = false

        if (isActive.get()) {
            broadcast("Cliente desconectado. Esperando...")
            updateNotification("Esperando conexión...")
        }
    }

    private fun processAudio(buffer: ByteArray, size: Int): ByteArray {
        if (isMuted) return ByteArray(size)
        val vol = volumeLevel
        if (vol >= 1.0f) return buffer
        val result = ByteArray(size)
        var i = 0
        while (i < size - 1) {
            val lo     = buffer[i].toInt() and 0xFF
            val hi     = buffer[i + 1].toInt()
            val sample = lo or (hi shl 8)
            val scaled = (sample * vol).toInt().coerceIn(-32768, 32767)
            result[i]     = (scaled and 0xFF).toByte()
            result[i + 1] = ((scaled shr 8) and 0xFF).toByte()
            i += 2
        }
        return result
    }

    // ── Notification ──────────────────────────────────────────────────────────

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "PhoneMic Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Streaming de micrófono activo"
                setShowBadge(false)
            }
            getSystemService(NotificationManager::class.java)
                ?.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(statusText: String): Notification {
        val pi = { action: String, reqCode: Int ->
            PendingIntent.getService(
                this, reqCode,
                Intent(this, MicService::class.java).apply { this.action = action },
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
        }
        val openApp = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("PhoneMic")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentIntent(openApp)
            .addAction(android.R.drawable.ic_delete,      "Detener",               pi(ACTION_STOP, 0))
            .addAction(android.R.drawable.ic_media_pause, if (isMuted) "Activar" else "Silenciar", pi(ACTION_TOGGLE_MUTE, 1))
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    private fun updateNotification(text: String = if (isMuted) "Silenciado" else "Transmitiendo audio") {
        getSystemService(NotificationManager::class.java)
            ?.notify(NOTIFICATION_ID, buildNotification(text))
    }

    // ── Broadcast ─────────────────────────────────────────────────────────────

    private fun broadcast(
        msg: String,
        streaming: Boolean = isActive.get(),
        connected: Boolean = isConnected
    ) {
        sendBroadcast(Intent(ACTION_STATUS_UPDATE).apply {
            setPackage(packageName)
            putExtra(EXTRA_STATUS_MSG,   msg)
            putExtra(EXTRA_IS_MUTED,     isMuted)
            putExtra(EXTRA_IS_STREAMING, streaming)
            putExtra(EXTRA_IS_CONNECTED, connected)
        })
    }

    // ── WakeLock ──────────────────────────────────────────────────────────────

    private fun acquireWakeLock() {
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "PhoneMic:MicServiceWakeLock"
        ).also { it.acquire(12 * 60 * 60 * 1000L) }
    }

    private fun releaseWakeLock() {
        try {
            if (wakeLock?.isHeld == true) wakeLock?.release()
        } catch (_: Exception) {}
        wakeLock = null
    }
}

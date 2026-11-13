package com.kizilelma.mobile

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

class AutonomousSessionService : Service() {
    companion object {
        const val ACTION_START = "com.kizilelma.mobile.action.START_AUTONOMOUS"
        const val ACTION_STOP = "com.kizilelma.mobile.action.STOP_AUTONOMOUS"
        private const val CHANNEL_ID = "kizil_elma_autonomous"
        private const val NOTIFICATION_ID = 7310
    }

    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID, "Kızıl Elma Otonom Sohbet", NotificationManager.IMPORTANCE_LOW
            ).apply { description = "Kullanıcı tarafından başlatılan çevrimdışı sohbet oturumu" }
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        val openApp = PendingIntent.getActivity(
            this, NOTIFICATION_ID, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            Notification.Builder(this, CHANNEL_ID) else Notification.Builder(this))
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Kızıl Elma · Otonom sohbet")
            .setContentText("Çevrimdışı oturum etkin")
            .setContentIntent(openApp)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .build()
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            } else startForeground(NOTIFICATION_ID, notification)
        } catch (_: Exception) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null
}

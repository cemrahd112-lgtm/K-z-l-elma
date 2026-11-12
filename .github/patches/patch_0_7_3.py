from pathlib import Path
import xml.etree.ElementTree as ET

R = Path(".")
M = R / "app/src/main/java/com/kizilelma/mobile/MainActivity.kt"
G = R / "app/build.gradle.kts"
A = R / "app/src/main/AndroidManifest.xml"
S = R / "app/src/main/java/com/kizilelma/mobile/AutonomousSessionService.kt"
m = M.read_text()
g = G.read_text()
manifest = ET.parse(A)
root = manifest.getroot()
android = "{http://schemas.android.com/apk/res/android}"
tools = "{http://schemas.android.com/tools}"

# 0.7.3 = versionCode 24. Do not silently patch an unexpected base.
if 'versionCode = 23' not in g or 'versionName = "0.7.2"' not in g:
    raise SystemExit("Unexpected pre-v0.7.3 version")
G.write_text(g.replace('versionCode = 23', 'versionCode = 24', 1).replace('versionName = "0.7.2"', 'versionName = "0.7.3"', 1))

# Add the foreground session service and explicit battery-optimization permission.
permissions = {x.get(android + "name") for x in root.findall("uses-permission")}
for name in ("android.permission.FOREGROUND_SERVICE", "android.permission.FOREGROUND_SERVICE_SPECIAL_USE", "android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS", "android.permission.POST_NOTIFICATIONS"):
    if name not in permissions:
        ET.SubElement(root, "uses-permission", {android + "name": name})

app = root.find("application")
if app is None:
    raise SystemExit("Manifest application element missing")
services = [x for x in app.findall("service") if x.get(android + "name") == ".AutonomousSessionService"]
if not services:
    svc = ET.SubElement(app, "service", {
        android + "name": ".AutonomousSessionService",
        android + "enabled": "true",
        android + "exported": "false",
        android + "stopWithTask": "false",
        android + "foregroundServiceType": "specialUse"
    })
    ET.SubElement(svc, "property", {
        android + "name": "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE",
        android + "value": "User-visible offline autonomous assistant session"
    })
ET.indent(manifest, space="    ")
manifest.write(A, encoding="utf-8", xml_declaration=True)

# A visible, user-started foreground notification keeps the session service alive.
S.write_text("""package com.kizilelma.mobile

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
        private const val CHANNEL_ID = "autonomous_session"
        private const val NOTIFICATION_ID = 7303
    }

    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Otonom Sohbet",
                NotificationManager.IMPORTANCE_LOW
            ).apply { description = "Kullanıcı tarafından başlatılan çevrimdışı asistan oturumu" }
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
            this, 7303, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            Notification.Builder(this, CHANNEL_ID) else Notification.Builder(this))
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Kızıl Elma · Otonom Sohbet")
            .setContentText("Çevrimdışı asistan oturumu etkin")
            .setContentIntent(openApp)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .build()
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (failure: Exception) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
""")

# SpeechRecognizer errors 11-13 must give an explicit offline Turkish pack instruction.
val oldErrorStart = '                                val explanation = when (error) {'
i = m.find(oldErrorStart)
if i < 0:
    raise SystemExit("v0.7.1 speech error explanation block missing")
j = m.find('                                if (liveChatEnabled) {', i)
if j < 0:
    raise SystemExit("Speech error cleanup anchor missing")
m = m[:i] + '''                                val explanation = when (error) {
                                    11, 12, 13 -> "Lütfen cihaz ayarlarından çevrimdışı Türkçe dil paketini indirin. (Ses tanıma hata kodu: $error)"
                                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Ses tanıma servisi meşgul (hata $error)."
                                    else -> "Çevrimdışı ses tanıma başarısız oldu (hata $error)."
                                }
''' + m[j:]

# createOnDeviceSpeechRecognizer and startListening may throw on OEM implementations.
# Existing catch remains the final crash barrier; make the user-facing guidance explicit.
m = m.replace(
    'val detail = "Çevrimdışı mikrofon başlatılamadı: ${failure.localizedMessage ?: failure.javaClass.simpleName}"',
    'val detail = "Çevrimdışı ses tanıma başlatılamadı. Lütfen cihaz ayarlarından çevrimdışı Türkçe dil paketini indirin. Ayrıntı: ${failure.localizedMessage ?: failure.javaClass.simpleName}"',
    1
)

# Foreground service lifecycle follows the explicit autonomous-mode toggle.
old_on = '''        if (liveChatEnabled) {
            binding.statusText.text = "Otonom sohbet aktif · Dinliyorum"
            startVoiceInput()
        } else {
            speechRecognizer?.cancel()
            tts?.stop()
            binding.statusText.text = "Otonom sohbet kapalı"
        }
'''
new_on = '''        if (liveChatEnabled) {
            startAutonomousForegroundSession()
            binding.statusText.text = "Otonom sohbet aktif · Dinliyorum"
            startVoiceInput()
        } else {
            stopAutonomousForegroundSession()
            speechRecognizer?.cancel()
            tts?.stop()
            binding.statusText.text = "Otonom sohbet kapalı"
        }
'''
if old_on not in m:
    raise SystemExit("Autonomous toggle body anchor missing")
m = m.replace(old_on, new_on, 1)

# Keep service state in sync when an STT/TTS failure disables autonomous mode.
m = m.replace('''                                    liveChatEnabled = false
                                    updateAutonomousButtonState()
''','''                                    liveChatEnabled = false
                                    updateAutonomousButtonState()
                                    stopAutonomousForegroundSession()
''')
m = m.replace('''            liveChatEnabled = false
            updateAutonomousButtonState()
            return
''','''            liveChatEnabled = false
            updateAutonomousButtonState()
            stopAutonomousForegroundSession()
            return
''')

# Request battery-optimization exemption once on first launch; Android still requires user approval.
anchor = '        autoLoadExistingLocalModel()'
if anchor not in m:
    raise SystemExit("MainActivity startup anchor missing")
m = m.replace(anchor, anchor + '\n        requestBatteryOptimizationExemptionOnce()', 1)

helpers = """
    private fun startAutonomousForegroundSession() {
        try {
            val intent = Intent(this, AutonomousSessionService::class.java).apply {
                action = AutonomousSessionService.ACTION_START
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
        } catch (failure: Exception) {
            appendChat("ASSISTANT", "Ön plan bildirimi başlatılamadı. HyperOS/MIUI arka plan kısıtlamaları otonom oturumu durdurabilir.")
        }
    }

    private fun stopAutonomousForegroundSession() {
        try {
            val intent = Intent(this, AutonomousSessionService::class.java).apply {
                action = AutonomousSessionService.ACTION_STOP
            }
            startService(intent)
        } catch (_: Exception) { }
    }

    private fun requestBatteryOptimizationExemptionOnce() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return
        val prefs = getSharedPreferences("runtime_guidance", MODE_PRIVATE)
        if (prefs.getBoolean("battery_prompt_shown", false)) return
        prefs.edit().putBoolean("battery_prompt_shown", true).apply()
        if (getSystemService(android.os.PowerManager::class.java).isIgnoringBatteryOptimizations(packageName)) return
        mainHandler.postDelayed({
            if (isFinishing || isDestroyed) return@postDelayed
            try {
                val intent = Intent(android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = android.net.Uri.parse("package:$packageName")
                }
                startActivity(intent)
            } catch (_: Exception) {
                appendChat("ASSISTANT", "Pil optimizasyonu istisnası otomatik açılamadı. Ayarlar > Uygulamalar > Kızıl Elma > Pil bölümünden arka plan kısıtlamalarını kontrol edin.")
            }
        }, 900)
    }

"""
if 'private fun startAutonomousForegroundSession()' not in m:
    pos = m.find('    private fun toggleLiveChat()')
    if pos < 0: raise SystemExit("toggleLiveChat method missing")
    m = m[:pos] + helpers + m[pos:]

# TTS local-only requirement is explicit: do not permit a network voice.
m = m.replace(
    'appendChat("ASSISTANT", "Çevrimdışı Türkçe TTS bulunamadı; canlı sohbet kapatıldı.")',
    'appendChat("ASSISTANT", "Cihazda çevrimdışı Türkçe ses bulunamadı. Lütfen cihaz ayarlarından çevrimdışı Türkçe TTS sesini indirin; canlı sohbet kapatıldı.")',
    1
)

M.write_text(m)

# Keep the model path strictly local and make CI assert there is no cloud inference client.
engine = R / "app/src/main/java/com/kizilelma/mobile/assistant/LocalLlmEngine.kt"
e = engine.read_text()
if not any(token in e for token in ("LlmInference", "LiteRt", "LiteRT", "Conversation")):
    raise SystemExit("Local inference engine implementation could not be identified")
for forbidden in ("OpenAI", "https://", "http://", "Retrofit", "OkHttpClient", "ktor.client"):
    if forbidden in e:
        raise SystemExit("Potential network inference dependency found in LocalLlmEngine.kt: " + forbidden)

(R / "CHANGELOG_0.7.3.md").write_text(
    "# Kızıl Elma Mobil 0.7.3\\n\\n"
    "- SpeechRecognizer başlatma/çalıştırma istisnaları güvenli biçimde yakalanır.\\n"
    "- STT hata 11/12/13 durumlarında çevrimdışı Türkçe dil paketi için açık yönlendirme gösterilir.\\n"
    "- Otonom oturum, kullanıcı etkinleştirdiğinde görünür ön plan servisi bildirimi kullanır.\\n"
    "- İlk açılışta Android pil optimizasyonu istisnası için kullanıcı onay ekranı sunulur.\\n"
    "- Qwen çıkarımı cihazdaki LiteRT-LM motoru ve yerel model dosyası üzerinden yapılır; inference katmanında ağ istemcisi bulunmaz.\\n"
    "- Version Code 24.\\n"
)

assert 'versionCode = 24' in G.read_text() and 'versionName = "0.7.3"' in G.read_text()
assert 'Lütfen cihaz ayarlarından çevrimdışı Türkçe dil paketini indirin' in m
assert 'startForegroundService(intent)' in m
assert 'ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS' in m
assert S.exists()
ET.parse(A)
print("v0.7.3 patch applied; manifest parsed; local-inference/network assertions passed")

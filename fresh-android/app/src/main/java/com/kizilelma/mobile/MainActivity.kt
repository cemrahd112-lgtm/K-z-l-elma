package com.kizilelma.mobile

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.SpeechService
import org.vosk.android.RecognitionListener
import org.json.JSONObject
import java.io.File
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {
    private lateinit var store: LocalStore
    private var tts: TextToSpeech? = null
    private var speech: SpeechService? = null
    private var voskModel: Model? = null
    private var ttsReady = false
    private var ttsInitFinished = false
    private val worker = Executors.newSingleThreadExecutor()
    private var voiceLoop = false
    private var modelPath: String? = null
    private var modelReady = false
    private val chatMessages = mutableStateListOf<Pair<String, String>>()
    private var statusText by mutableStateOf("Yerel mod · Ağ erişimi kapalı")
    private var processing = false
    private var lastRecognizedText = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = LocalStore(this)
        chatMessages.addAll(store.history())
        tts = TextToSpeech(this, this)
        modelPath = File(filesDir, "model.gguf").takeIf { it.isFile && it.length() > 0 }?.absolutePath
        val localSpeech = File(filesDir, "vosk-model")
        if (File(localSpeech, "am/final.mdl").exists()) {
            runCatching { voskModel = Model(localSpeech.absolutePath) }
                .onFailure { statusText = "STT modeli açılamadı: ${it.message}" }
        }
        modelPath?.let { path ->
            worker.execute {
                val loaded = runCatching { LlamaBridge.loadModel(path, 4096) }.getOrDefault(false)
                runOnUiThread {
                    modelReady = loaded
                    statusText = if (loaded) "Yerel yapay zekâ hazır · Çevrimdışı" else "GGUF modeli yüklenemedi"
                }
            }
        } ?: run { statusText = "GGUF modeli seçilmedi · Yerel sohbet hazır değil" }
        setContent { Screen() }
    }

    override fun onInit(status: Int) {
        ttsInitFinished = true
        ttsReady = status == TextToSpeech.SUCCESS &&
            (tts?.voices?.any { !it.isNetworkConnectionRequired && it.locale.language == "tr" } == true)
        if (!ttsReady && statusText.contains("Yerel mod")) {
            statusText = "Türkçe çevrimdışı TTS bulunamadı · Metin yanıtı kullanılabilir"
        }
    }

    override fun onResume() {
        super.onResume()
        if (voiceLoop && hasVoiceModels() && hasMicPermission()) beginListen()
    }

    private fun hasVoiceModels() = modelReady && voskModel != null
    private fun hasMicPermission() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun beginListen() {
        if (!voiceLoop || !hasVoiceModels() || speech != null || processing) return
        try {
            val recognizer = Recognizer(voskModel, 16000.0f)
            val handled = AtomicBoolean(false)
            speech = SpeechService(recognizer, 16000.0f).also { service ->
                service.startListening(object : RecognitionListener {
                    override fun onPartialResult(hypothesis: String?) {
                        runOnUiThread { if (voiceLoop) statusText = "Dinliyorum… konuşmanızı bekliyorum" }
                    }
                    override fun onResult(hypothesis: String?) {
                        acceptSpeechResult(hypothesis, handled)
                    }
                    override fun onFinalResult(hypothesis: String?) {
                        acceptSpeechResult(hypothesis, handled)
                    }
                    override fun onError(exception: Exception?) {
                        stopSpeech()
                        runOnUiThread {
                            voiceLoop = false
                            stopAutonomousService()
                            statusText = "Ses tanıma hatası · Metin girişi kullanılabilir"
                            addAssistant("Çevrimdışı ses tanıma durdu. Türkçe Vosk modeli ve mikrofon iznini kontrol edin. Metin girişine döndüm.")
                        }
                    }
                    override fun onTimeout() {
                        stopSpeech()
                        if (voiceLoop) runOnUiThread { beginListen() }
                    }
                })
            }
            statusText = "Otonom sohbet açık · Dinliyorum"
        } catch (failure: Exception) {
            stopSpeech()
            voiceLoop = false
            stopAutonomousService()
            statusText = "Ses tanıma başlatılamadı · Metin girişi kullanılabilir"
            addAssistant("Mikrofon veya çevrimdışı STT başlatılamadı: ${failure.localizedMessage ?: failure.javaClass.simpleName}")
        }
    }

    private fun acceptSpeechResult(hypothesis: String?, handled: AtomicBoolean) {
        val text = runCatching { JSONObject(hypothesis ?: "{}").optString("text").trim() }.getOrDefault("")
        if (text.isNotBlank() && handled.compareAndSet(false, true)) {
            lastRecognizedText = text
            process(text, true)
        }
    }

    private fun stopSpeech() {
        runCatching { speech?.stop() }
        speech = null
    }

    private fun addMessage(role: String, body: String) {
        store.add(role, body)
        runOnUiThread { chatMessages.add(role to body) }
    }

    private fun addAssistant(body: String) = addMessage("ASSISTANT", body)

    private fun process(text: String, speak: Boolean) {
        if (processing || text.isBlank()) return
        processing = true
        stopSpeech()
        addMessage("USER", text.trim())
        statusText = "Yerel model yanıt hazırlıyor…"
        worker.execute {
            val answer = runCatching {
                check(modelReady) { "GGUF modeli yüklenmedi. Önce yerel modeli seçin." }
                LlamaBridge.generate(
                    "You are Kızıl Elma, a private offline Android assistant. Answer in Turkish, directly and accurately. Do not claim actions you did not perform. If unsure, say so.\\nUser: ${text.trim()}\\nAssistant:",
                    256
                ).trim()
            }.getOrElse { "Yerel model yanıt üretemedi: ${it.localizedMessage ?: it.javaClass.simpleName}" }
            runOnUiThread {
                processing = false
                addAssistant(answer.ifBlank { "Yerel model boş yanıt üretti." })
                if (speak && voiceLoop) {
                    if (ttsReady && ttsInitFinished) {
                        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                            override fun onStart(id: String?) {}
                            override fun onDone(id: String?) {
                                runOnUiThread { if (voiceLoop && !isFinishing && !isDestroyed) beginListen() }
                            }
                            override fun onError(id: String?) {
                                runOnUiThread {
                                    voiceLoop = false
                                    stopAutonomousService()
                                    statusText = "TTS hatası · Metin girişi kullanılabilir"
                                }
                            }
                        })
                        val result = tts?.speak(answer, TextToSpeech.QUEUE_FLUSH, null, "reply-${System.currentTimeMillis()}")
                        if (result == TextToSpeech.ERROR) {
                            voiceLoop = false
                            stopAutonomousService()
                            statusText = "Sesli yanıt verilemedi · Metin yanıtı hazır"
                        } else statusText = "Yanıt seslendiriliyor…"
                    } else {
                        voiceLoop = false
                        stopAutonomousService()
                        statusText = "Türkçe çevrimdışı TTS bulunamadı · Metin yanıtı hazır"
                        addAssistant("Bu cihazda Türkçe çevrimdışı seslendirme bulunamadığı için sesli döngü durduruldu.")
                    }
                } else {
                    statusText = if (voiceLoop) "Yanıt hazır · Yeniden dinleniyor" else "Yanıt hazır · Çevrimdışı"
                    if (voiceLoop) beginListen()
                }
            }
        }
    }

    private fun startAutonomousService() {
        runCatching {
            val intent = Intent(this, AutonomousSessionService::class.java).apply {
                action = AutonomousSessionService.ACTION_START
            }
            ContextCompat.startForegroundService(this, intent)
        }.onFailure {
            statusText = "Ön plan oturumu başlatılamadı · Uygulama açıkken kullanın"
        }
    }

    private fun stopAutonomousService() {
        runCatching {
            startService(Intent(this, AutonomousSessionService::class.java).apply {
                action = AutonomousSessionService.ACTION_STOP
            })
        }
    }

    private fun stopVoice() {
        voiceLoop = false
        stopSpeech()
        runCatching { tts?.stop() }
        stopAutonomousService()
        statusText = "Sesli sohbet durduruldu"
    }

    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && hasVoiceModels()) {
            voiceLoop = true
            startAutonomousService()
            beginListen()
        } else {
            voiceLoop = false
            statusText = if (granted) "Önce GGUF ve STT modellerini yükleyin" else "Mikrofon izni verilmedi"
        }
    }

    @Composable
    private fun Screen() {
        var input by remember { mutableStateOf("") }
        var settingsExpanded by remember { mutableStateOf(false) }
        val listState = rememberLazyListState()
        val ggufPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) {
                statusText = "GGUF modeli içe aktarılıyor…"
                worker.execute {
                    val loaded = runCatching {
                        contentResolver.openInputStream(uri)!!.use { source ->
                            File(filesDir, "model.gguf").outputStream().use(source::copyTo)
                        }
                        val path = File(filesDir, "model.gguf").absolutePath
                        check(LlamaBridge.loadModel(path, 4096))
                        modelPath = path
                        true
                    }.getOrElse { statusText = "Model yüklenemedi: ${it.localizedMessage}"; false }
                    runOnUiThread {
                        modelReady = loaded
                        statusText = if (loaded) "GGUF modeli hazır · Çevrimdışı" else "GGUF modeli yüklenemedi"
                    }
                }
            }
        }
        val voskPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            if (uri != null) {
                statusText = "STT modeli içe aktarılıyor…"
                worker.execute {
                    val loaded = runCatching {
                        val dest = File(filesDir, "vosk-model").apply { deleteRecursively(); mkdirs() }
                        val root = androidx.documentfile.provider.DocumentFile.fromTreeUri(this@MainActivity, uri)!!
                        fun copyTree(src: androidx.documentfile.provider.DocumentFile, dst: File) {
                            dst.mkdirs()
                            src.listFiles().forEach { child ->
                                val target = File(dst, child.name ?: "data")
                                if (child.isDirectory) copyTree(child, target)
                                else contentResolver.openInputStream(child.uri)?.use { source ->
                                    target.outputStream().use(source::copyTo)
                                }
                            }
                        }
                        copyTree(root, dest)
                        val candidate = Model(dest.absolutePath)
                        runOnUiThread { voskModel?.close(); voskModel = candidate }
                        true
                    }.getOrElse { statusText = "STT modeli açılamadı: ${it.localizedMessage}"; false }
                    runOnUiThread { if (loaded) statusText = "Yerel STT modeli hazır" }
                }
            }
        }

        LaunchedEffect(chatMessages.size) {
            if (chatMessages.isNotEmpty()) listState.animateScrollToItem(chatMessages.lastIndex)
        }

        MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFF6650A4), secondary = Color(0xFF625B71))) {
            Column(
                Modifier.fillMaxSize().background(Color(0xFFF7F5FA)).padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.weight(1f)) {
                        Text("KIZIL ELMA MOBİL", style = MaterialTheme.typography.headlineSmall, color = Color(0xFF211B2B))
                        Text(statusText, style = MaterialTheme.typography.bodyMedium, color = Color(0xFF625B71))
                    }
                    IconButton(onClick = { settingsExpanded = !settingsExpanded }) {
                        Text(if (settingsExpanded) "×" else "⋮", style = MaterialTheme.typography.headlineMedium)
                    }
                }
                if (settingsExpanded) {
                    Card(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("ÇEVRİMDIŞI MODEL AYARLARI", style = MaterialTheme.typography.labelLarge)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedButton(onClick = { ggufPicker.launch(arrayOf("*/*")) }, modifier = Modifier.weight(1f)) { Text("GGUF modeli seç") }
                                OutlinedButton(onClick = { voskPicker.launch(null) }, modifier = Modifier.weight(1f)) { Text("STT modeli seç") }
                            }
                            Text("LLM: ${if (modelReady) "Hazır" else "Yüklenmedi"}  ·  STT: ${if (voskModel != null) "Hazır" else "Yüklenmedi"}  ·  TTS: ${if (ttsReady) "Hazır" else "Kullanılamıyor"}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                LazyColumn(
                    modifier = Modifier.weight(1f).fillMaxWidth(),
                    state = listState,
                    contentPadding = PaddingValues(vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    itemsIndexed(chatMessages) { _, item ->
                        val user = item.first == "USER"
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = if (user) Arrangement.End else Arrangement.Start) {
                            Surface(
                                color = if (user) Color(0xFFE8DFF8) else Color.White,
                                shape = RoundedCornerShape(18.dp),
                                tonalElevation = 1.dp,
                                modifier = Modifier.widthIn(max = 320.dp)
                            ) {
                                Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                                    Text(if (user) "SEN" else "KIZIL ELMA", style = MaterialTheme.typography.labelSmall, color = Color(0xFF625B71))
                                    Spacer(Modifier.height(3.dp))
                                    Text(item.second, style = MaterialTheme.typography.bodyLarge, color = Color(0xFF211B2B))
                                }
                            }
                        }
                    }
                }
                Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = input,
                        onValueChange = { input = it },
                        modifier = Modifier.weight(1f),
                        label = { Text("Mesaj") },
                        maxLines = 4,
                        enabled = !processing
                    )
                    Button(
                        onClick = {
                            val message = input.trim()
                            if (message.isNotEmpty() && !processing) {
                                if (!modelReady) {
                                    statusText = "Önce Ayarlar bölümünden GGUF modelini seçin"
                                } else {
                                    process(message, false)
                                    input = ""
                                }
                            }
                        },
                        enabled = input.isNotBlank() && !processing,
                        modifier = Modifier.height(56.dp)
                    ) { Text("Gönder") }
                }
                Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = {
                            if (!hasVoiceModels()) statusText = "Sesli sohbet için GGUF ve Vosk modellerini yükleyin"
                            else if (!hasMicPermission()) micPermission.launch(Manifest.permission.RECORD_AUDIO)
                            else {
                                voiceLoop = true
                                startAutonomousService()
                                beginListen()
                            }
                        },
                        modifier = Modifier.weight(1f),
                        enabled = !voiceLoop
                    ) { Text("Otonom sohbeti başlat") }
                    OutlinedButton(onClick = { stopVoice() }, modifier = Modifier.weight(0.7f), enabled = voiceLoop) {
                        Text("Durdur")
                    }
                }
            }
        }
    }

    override fun onDestroy() {
        stopVoice()
        stopSpeech()
        runCatching { tts?.stop(); tts?.shutdown(); voskModel?.close(); LlamaBridge.unload() }
        worker.shutdownNow()
        store.close()
        super.onDestroy()
    }
}

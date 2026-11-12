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
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
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

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {
    private lateinit var store: LocalStore
    private var tts: TextToSpeech? = null
    private var speech: SpeechService? = null
    private var voskModel: Model? = null
    private var ttsReady = false
    private val worker = Executors.newSingleThreadExecutor()
    private var voiceLoop = false
    private var modelPath: String? = null
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = LocalStore(this)
        tts = TextToSpeech(this, this)
        modelPath = File(filesDir, "model.gguf").takeIf { it.exists() }?.absolutePath
        runCatching {
            modelPath?.let { check(LlamaBridge.loadModel(it, 4096)) }
            val localSpeech = File(filesDir, "vosk-model")
            if (File(localSpeech, "am/final.mdl").exists()) voskModel = Model(localSpeech.absolutePath)
        }
        setContent { Screen() }
    }
    override fun onInit(status: Int) {
        ttsReady = status == TextToSpeech.SUCCESS && (tts?.voices?.any { !it.isNetworkConnectionRequired && it.locale.language == "tr" } == true)
    }
    override fun onResume() {
        super.onResume()
        val ready = modelPath != null && voskModel != null
        if (ready && ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            voiceLoop = true
            beginListen()
        }
    }
    private fun beginListen() {
        if (!voiceLoop || modelPath == null || voskModel == null || speech != null) return
        try {
            val recognizer = Recognizer(voskModel, 16000.0f)
            speech = SpeechService(recognizer, 16000.0f).also { service ->
                service.startListening(object : RecognitionListener {
                    override fun onPartialResult(hypothesis: String?) = Unit
                    override fun onResult(hypothesis: String?) {
                        val text = runCatching { JSONObject(hypothesis ?: "{}").optString("text") }.getOrDefault("")
                        if (text.isNotBlank()) process(text, true)
                    }
                    override fun onFinalResult(hypothesis: String?) {
                        val text = runCatching { JSONObject(hypothesis ?: "{}").optString("text") }.getOrDefault("")
                        if (text.isNotBlank()) process(text, true)
                    }
                    override fun onError(exception: Exception?) { stopSpeech(); runOnUiThread { voiceLoop = false } }
                    override fun onTimeout() { stopSpeech(); if (voiceLoop) beginListen() }
                })
            }
        } catch (_: Exception) { stopSpeech(); voiceLoop = false }
    }
    private fun stopSpeech() { runCatching { speech?.stop() }; speech = null }
    private fun process(text: String, speak: Boolean) {
        stopSpeech()
        store.add("USER", text)
        worker.execute {
            val answer = runCatching { LlamaBridge.generate("You are Kızıl Elma. Answer in Turkish.\\nUser: $text\\nAssistant:", 256) }
                .getOrElse { "Yerel model yanıt üretemedi: ${it.javaClass.simpleName}" }
            store.add("ASSISTANT", answer)
            runOnUiThread {
                if (speak && ttsReady) {
                    tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                        override fun onStart(id: String?) {}
                        override fun onDone(id: String?) { if (voiceLoop) beginListen() }
                        override fun onError(id: String?) { voiceLoop = false }
                    })
                    tts?.speak(answer, TextToSpeech.QUEUE_FLUSH, null, "reply-${System.currentTimeMillis()}")
                } else if (voiceLoop) { voiceLoop = false }
            }
        }
    }
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && modelPath != null && voskModel != null) { voiceLoop = true; beginListen() }
    }
    @Composable private fun Screen() {
        var messages by remember { mutableStateOf(store.history()) }
        var input by remember { mutableStateOf("") }
        var status by remember { mutableStateOf("Yerel mod · Ağ izni yok") }
        val ggufPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) runCatching {
                contentResolver.openInputStream(uri)!!.use { it.copyTo(File(filesDir, "model.gguf").outputStream()) }
                modelPath = File(filesDir, "model.gguf").absolutePath
                check(LlamaBridge.loadModel(modelPath!!, 4096))
                status = "GGUF modeli yüklendi"
            }.onFailure { status = "Model yüklenemedi: ${it.message}" }
        }
        val voskPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            if (uri != null) runCatching {
                val dest = File(filesDir, "vosk-model").apply { deleteRecursively(); mkdirs() }
                val root = androidx.documentfile.provider.DocumentFile.fromTreeUri(this@MainActivity, uri)!!
                fun copyTree(src: androidx.documentfile.provider.DocumentFile, dst: File) {
                    dst.mkdirs()
                    src.listFiles().forEach { child ->
                        val target = File(dst, child.name ?: "data")
                        if (child.isDirectory) copyTree(child, target)
                        else contentResolver.openInputStream(child.uri)?.use { input -> target.outputStream().use(input::copyTo) }
                    }
                }
                copyTree(root, dest)
                voskModel?.close(); voskModel = Model(dest.absolutePath)
                status = "Yerel STT modeli hazır"
            }.onFailure { status = "STT modeli açılamadı: ${it.message}" }
        }
        MaterialTheme {
            Column(Modifier.fillMaxSize().padding(16.dp)) {
                Text("KIZIL ELMA MOBİL", style = MaterialTheme.typography.headlineSmall)
                Text(status)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { ggufPicker.launch(arrayOf("*/*")) }) { Text("GGUF seç") }
                    Button(onClick = { voskPicker.launch(null) }) { Text("STT modeli seç") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = {
                        if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
                            micPermission.launch(Manifest.permission.RECORD_AUDIO)
                        else { voiceLoop = true; beginListen(); status = "Otonom dinleme açık" }
                    }) { Text("Sesli sohbeti başlat") }
                    OutlinedButton(onClick = { voiceLoop = false; stopSpeech(); tts?.stop(); status = "Sesli sohbet durduruldu" }) { Text("Durdur") }
                }
                LazyColumn(Modifier.weight(1f)) {
                    items(messages) { (role, body) -> Text("$role: $body", Modifier.padding(vertical = 6.dp)) }
                }
                OutlinedTextField(input, { input = it }, Modifier.fillMaxWidth(), label = { Text("Mesaj") })
                Button(onClick = { if (input.isNotBlank()) { process(input, false); input = ""; messages = store.history() } }) { Text("Gönder") }
            }
        }
    }
    override fun onDestroy() {
        voiceLoop = false; stopSpeech(); runCatching { tts?.stop(); tts?.shutdown(); voskModel?.close(); LlamaBridge.unload() }
        worker.shutdownNow(); store.close(); super.onDestroy()
    }
}

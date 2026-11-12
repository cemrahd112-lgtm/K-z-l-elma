from pathlib import Path
import re

ROOT = Path(".")
MAIN = ROOT / "app/src/main/java/com/kizilelma/mobile/MainActivity.kt"
ENGINE = ROOT / "app/src/main/java/com/kizilelma/mobile/assistant/LocalLlmEngine.kt"
LAYOUT = ROOT / "app/src/main/res/layout/activity_main.xml"
GRADLE = ROOT / "app/build.gradle.kts"

main = MAIN.read_text()
engine = ENGINE.read_text()
layout = LAYOUT.read_text()
gradle = GRADLE.read_text()

# 1. Dark message composer with fixed foreground and hint colors.
pattern = r'(<EditText\s+android:id="@\+id/commandInput"[\s\S]*?android:background=")[^"]*("[\s\S]*?android:hint="[^"]*"\s+android:inputType="[^"]*"\s+android:textColor=")[^"]*("\s+android:textColorHint=")[^"]*(")'
layout, count = re.subn(pattern, r'\g<1>#1E293B\g<2>#FFFFFF\g<3>#94A3B8\g<4>', layout, count=1)
if count != 1:
    raise SystemExit("commandInput color block not found")
LAYOUT.write_text(layout)

# 2. Keep the real file-size + SHA-256 validation in ModelDownloader, and expose
#    native inference exceptions instead of swallowing them.
new_response = "val response = activeConversation.sendMessage(safePrompt).contents.toString().trim()"
if new_response not in engine:
    for old_response in (
        "val response = activeConversation.sendMessage(safePrompt).text.trim()",
        "val response = activeConversation.sendMessage(safePrompt).toString().trim()",
    ):
        if old_response in engine:
            engine = engine.replace(old_response, new_response, 1)
            break
    else:
        raise SystemExit("LocalLlmEngine response extraction code not found")
engine = engine.replace(
    'error(callback, failure.localizedMessage ?: "Model yanıt üretemedi")',
    'error(callback, "${failure.javaClass.simpleName}: ${failure.localizedMessage ?: "Model yanıt üretemedi"}")',
    1,
)
ENGINE.write_text(engine)

# 3. Use SpeechRecognizer directly; do not launch the external Google recognition UI.
if "import android.speech.RecognitionListener" not in main:
    main = main.replace(
        "import android.speech.RecognizerIntent\n",
        "import android.speech.RecognizerIntent\nimport android.speech.RecognitionListener\n",
        1,
    )
if "private var speechRecognizer: SpeechRecognizer? = null" not in main:
    main = main.replace(
        "    private var tts: TextToSpeech? = null\n",
        "    private var tts: TextToSpeech? = null\n    private var speechRecognizer: SpeechRecognizer? = null\n",
        1,
    )
start = main.find("    private fun startVoiceInput() {")
end = main.find("\n    private fun processCommand(raw: String)", start)
if start < 0 or end < 0:
    raise SystemExit("startVoiceInput method not found")
voice = """    private fun startVoiceInput() {
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), microphonePermissionRequest)
            return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            binding.resultText.text = "Ses tanıma hizmeti bu cihazda kullanılamıyor."
            return
        }
        try {
            speechRecognizer?.cancel()
            speechRecognizer?.destroy()
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).apply {
                setRecognitionListener(object : RecognitionListener {
                    override fun onReadyForSpeech(params: Bundle?) {
                        runOnUiThread { binding.resultText.text = "Dinleniyor..." }
                    }
                    override fun onBeginningOfSpeech() {
                        runOnUiThread { binding.resultText.text = "Dinleniyor..." }
                    }
                    override fun onRmsChanged(rmsdB: Float) = Unit
                    override fun onBufferReceived(buffer: ByteArray?) = Unit
                    override fun onEndOfSpeech() {
                        runOnUiThread { binding.resultText.text = "Ses çözümleniyor..." }
                    }
                    override fun onError(error: Int) {
                        runOnUiThread {
                            if (!isFinishing && !isDestroyed) binding.resultText.text =
                                "Ses tanıma hatası (kod: $error). Tekrar deneyebilirsiniz."
                        }
                    }
                    override fun onResults(results: Bundle?) {
                        val spoken = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                            ?.firstOrNull().orEmpty()
                        runOnUiThread {
                            if (!isFinishing && !isDestroyed) {
                                if (spoken.isNotBlank()) {
                                    binding.commandInput.setText(spoken)
                                    binding.commandInput.setSelection(spoken.length)
                                    binding.resultText.text = "Ses metne aktarıldı. Göndermek için oka basın."
                                } else binding.resultText.text = "Anlaşılır bir konuşma algılanamadı."
                            }
                        }
                    }
                    override fun onPartialResults(partialResults: Bundle?) {
                        val partial = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                            ?.firstOrNull().orEmpty()
                        if (partial.isNotBlank()) runOnUiThread {
                            if (!isFinishing && !isDestroyed) binding.commandInput.setText(partial)
                        }
                    }
                    override fun onEvent(eventType: Int, params: Bundle?) = Unit
                })
            }
            binding.resultText.text = "Dinleniyor..."
            val recognitionIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "tr-TR")
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            }
            speechRecognizer?.startListening(recognitionIntent)
        } catch (failure: Exception) {
            binding.resultText.text =
                "Mikrofon başlatılamadı: ${failure.localizedMessage ?: failure.javaClass.simpleName}"
            speechRecognizer?.destroy()
            speechRecognizer = null
        }
    }
"""
main = main[:start] + voice + main[end:]

# If model startup failed while a user prompt was queued, show the failure as an assistant bubble.
main = main.replace(
    '                    binding.modelStatusText.text = "Yerel model başlatılamadı: $message"',
    '                    binding.modelStatusText.text = "Yerel model başlatılamadı: $message"\n'
    '                    val queued = pendingLocalPrompt\n'
    '                    pendingLocalPrompt = null\n'
    '                    if (!queued.isNullOrBlank()) appendChat("ASSISTANT", "Hata: Model yüklenemedi - $message")',
    1,
)

# Missing/invalid model must be visible in chat, not only in the status line.
main = main.replace(
    '                val notice = "Qwen3-0.6B yerel modeli henüz indirilmemiş. Yerel yanıt için modeli indir/yükle düğmesini kullanın."\n'
    '                binding.resultText.text = notice\n'
    '                appendChat("SYSTEM", notice)',
    '                val notice = "Qwen3-0.6B yerel modeli henüz indirilmemiş. Yerel yanıt için modeli indir/yükle düğmesini kullanın."\n'
    '                binding.resultText.text = notice\n'
    '                appendChat("ASSISTANT", notice)',
    1,
)
main = main.replace(
    '                        appendChat("SYSTEM", notice)',
    '                        appendChat("ASSISTANT", notice)',
    1,
)

# Runtime inference errors are shown in the conversation as assistant messages.
main = main.replace(
    '                    binding.resultText.text = "Yerel model hatası: $message"\n'
    '                    memory.appendChatMessage("SYSTEM", "Yerel model hatası: $message")\n'
    '                    renderChatHistory()',
    '                    val diagnostic = "Hata: Model yanıtı üretilemedi - $message"\n'
    '                    binding.resultText.text = diagnostic\n'
    '                    memory.appendChatMessage("ASSISTANT", diagnostic)\n'
    '                    renderChatHistory()',
    1,
)

# Release SpeechRecognizer resources with the Activity.
main = main.replace(
    "        tts?.stop()\n        tts?.shutdown()",
    "        speechRecognizer?.cancel()\n        speechRecognizer?.destroy()\n        speechRecognizer = null\n"
    "        tts?.stop()\n        tts?.shutdown()",
    1,
)
MAIN.write_text(main)

if 'versionCode = 19' not in gradle or 'versionName = "0.6.6"' not in gradle:
    raise SystemExit("v0.6.6 version fields not found before 0.6.7 bump")
gradle = gradle.replace("versionCode = 19", "versionCode = 20", 1)
gradle = gradle.replace('versionName = "0.6.6"', 'versionName = "0.6.7"', 1)
GRADLE.write_text(gradle)

assert 'SpeechRecognizer.createSpeechRecognizer(this)' in main
assert 'startActivityForResult(intent, speechRequest)' not in main
assert 'android:background="#1E293B"' in layout
assert 'android:textColor="#FFFFFF"' in layout
assert 'android:textColorHint="#94A3B8"' in layout
assert 'versionCode = 20' in gradle and 'versionName = "0.6.7"' in gradle
print("Applied v0.6.7 fixes.")

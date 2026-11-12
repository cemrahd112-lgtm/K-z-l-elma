from pathlib import Path
import xml.etree.ElementTree as ET
R=Path(".")
M=R/"app/src/main/java/com/kizilelma/mobile/MainActivity.kt"
E=R/"app/src/main/java/com/kizilelma/mobile/assistant/LocalLlmEngine.kt"
D=R/"app/src/main/java/com/kizilelma/mobile/assistant/ModelDownloader.kt"
G=R/"app/build.gradle.kts"
A=R/"app/src/main/AndroidManifest.xml"
L=R/"app/src/main/res/layout/activity_main.xml"
m=M.read_text(); e=E.read_text()
D.write_text(D.read_text().replace("KizilElmaMobil/0.6.3","KizilElmaMobil/0.7.0",1))
m=m.replace("import android.speech.RecognizerIntent\n","import android.speech.RecognizerIntent\nimport android.speech.RecognitionListener\n",1)
m=m.replace("import android.speech.tts.TextToSpeech\n","import android.speech.tts.TextToSpeech\nimport android.speech.tts.UtteranceProgressListener\n",1)
m=m.replace("import android.widget.Toast\n","import android.widget.Toast\nimport android.widget.Button\nimport android.widget.Switch\nimport com.google.android.material.bottomsheet.BottomSheetDialog\n",1)
m=m.replace("    private var tts: TextToSpeech? = null\n","""    private var tts: TextToSpeech? = null
    private var speechRecognizer: SpeechRecognizer? = null
    private var toolsDialog: BottomSheetDialog? = null
    private var liveChatEnabled = false
    private var offlineTtsAvailable = false
    private val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())
""",1)
m=m.replace("    private val speechRequest = 4103\n","",1)
old="""        binding.modelStatusText.text = LocalModelStatus.describe(this)
        renderChatHistory()
        binding.modelButton.setOnClickListener { installOrLoadLocalModel() }
        binding.voiceReplySwitch.setOnCheckedChangeListener { _, enabled ->
            voiceRepliesEnabled = enabled
            if (!enabled) tts?.stop()
        }
        binding.settingsToggleButton.setOnClickListener {
            binding.settingsPanel.visibility = if (binding.settingsPanel.visibility == android.view.View.VISIBLE)
                android.view.View.GONE else android.view.View.VISIBLE
        }

        binding.accessibilityButton.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        binding.screenButton.setOnClickListener { requestScreenCapture() }
        binding.stopButton.setOnClickListener {
            ScreenCaptureService.stop(this)
            binding.statusText.text = "Durum: Durduruldu"
            speak("Ekran analizi durduruldu")
        }
        binding.voiceButton.setOnClickListener { startVoiceInput() }
        binding.runButton.setOnClickListener {
            val message = binding.commandInput.text.toString()
            binding.commandInput.text.clear()
            processCommand(message)
        }

    }
"""
new="""        binding.modelStatusText.text = "Model kontrol ediliyor..."
        binding.statusText.text = "Çevrimdışı asistan başlatılıyor"
        renderChatHistory()
        binding.settingsToggleButton.setOnClickListener { showToolsSheet() }
        binding.voiceButton.setOnClickListener { startVoiceInput() }
        binding.liveChatButton.setOnClickListener { toggleLiveChat() }
        binding.runButton.setOnClickListener {
            val message = binding.commandInput.text.toString()
            binding.commandInput.text.clear()
            processCommand(message)
        }
        autoLoadExistingLocalModel()
    }
"""
if old not in m: raise SystemExit("onCreate anchor missing")
m=m.replace(old,new,1)
a=m.index('    @Deprecated("Activity result kept for compatibility with the project baseline")')
b=m.index('    private fun processCommand(raw: String)',a)
voice="""    @Deprecated("Activity result kept for compatibility with the project baseline")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == projectionRequest) {
            if (resultCode == Activity.RESULT_OK && data != null) {
                val serviceIntent = Intent(this, ScreenCaptureService::class.java).apply {
                    putExtra(ScreenCaptureService.EXTRA_RESULT_CODE, resultCode)
                    putExtra(ScreenCaptureService.EXTRA_RESULT_DATA, data)
                }
                try {
                    if (Build.VERSION.SDK_INT >= 26) startForegroundService(serviceIntent) else startService(serviceIntent)
                    binding.statusText.text = "Ekran analizi başlatılıyor"
                } catch (failure: Exception) {
                    binding.statusText.text = "Ekran servisi başlatılamadı: \${failure.localizedMessage}"
                    appendChat("ASSISTANT", "Ekran servisi başlatılamadı: \${failure.localizedMessage}")
                }
            } else binding.statusText.text = "Ekran izni verilmedi"
        }
    }

    private fun toggleLiveChat() {
        liveChatEnabled = !liveChatEnabled
        if (liveChatEnabled) {
            binding.liveChatButton.text = "Canlı sohbeti bitir"
            startVoiceInput()
        } else {
            binding.liveChatButton.text = "Canlı konuşma"
            speechRecognizer?.cancel()
            tts?.stop()
            binding.statusText.text = "Canlı sohbet kapalı"
        }
    }

    private fun startVoiceInput() {
        if (Build.VERSION.SDK_INT < 31 || !SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            binding.statusText.text = "Çevrimdışı STT kullanılamıyor"
            appendChat("ASSISTANT", "Bu cihazda yerel çevrimdışı konuşma tanıma hizmeti bulunamadı. Ağ üzerinden tanımaya geçilmedi.")
            liveChatEnabled = false
            binding.liveChatButton.text = "Canlı konuşma"
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), microphonePermissionRequest)
            return
        }
        try {
            speechRecognizer?.cancel()
            speechRecognizer?.destroy()
            speechRecognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(this).apply {
                setRecognitionListener(object : RecognitionListener {
                    override fun onReadyForSpeech(params: Bundle?) { runOnUiThread { binding.statusText.text = "Dinliyorum..." } }
                    override fun onBeginningOfSpeech() { runOnUiThread { binding.statusText.text = "Dinliyorum..." } }
                    override fun onRmsChanged(rmsdB: Float) = Unit
                    override fun onBufferReceived(buffer: ByteArray?) = Unit
                    override fun onEndOfSpeech() { runOnUiThread { binding.statusText.text = "Düşünüyor..." } }
                    override fun onError(error: Int) {
                        runOnUiThread {
                            if (isFinishing || isDestroyed) return@runOnUiThread
                            binding.statusText.text = "Ses tanıma hatası ($error)"
                            if (liveChatEnabled && error in listOf(SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT, SpeechRecognizer.ERROR_RECOGNIZER_BUSY)) {
                                mainHandler.postDelayed({ if (liveChatEnabled) startVoiceInput() }, 700)
                            } else if (liveChatEnabled) {
                                appendChat("ASSISTANT", "Çevrimdışı ses tanıma durdu. Hata kodu: $error")
                                liveChatEnabled = false
                                binding.liveChatButton.text = "Canlı konuşma"
                            }
                        }
                    }
                    override fun onResults(results: Bundle?) {
                        val spoken = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                        runOnUiThread {
                            if (isFinishing || isDestroyed) return@runOnUiThread
                            if (spoken.isBlank()) {
                                if (liveChatEnabled) startVoiceInput() else binding.statusText.text = "Konuşma algılanamadı"
                                return@runOnUiThread
                            }
                            binding.commandInput.setText(spoken)
                            binding.commandInput.setSelection(spoken.length)
                            processCommand(spoken, forceLocalChat = liveChatEnabled)
                        }
                    }
                    override fun onPartialResults(partialResults: Bundle?) {
                        val partial = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                        if (partial.isNotBlank()) runOnUiThread { if (!isFinishing && !isDestroyed) binding.commandInput.setText(partial) }
                    }
                    override fun onEvent(eventType: Int, params: Bundle?) = Unit
                })
            }
            val speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "tr-TR")
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            }
            binding.statusText.text = "Dinliyorum..."
            speechRecognizer?.startListening(speechIntent)
        } catch (failure: Exception) {
            val detail = "Çevrimdışı mikrofon başlatılamadı: \${failure.localizedMessage ?: failure.javaClass.simpleName}"
            binding.statusText.text = detail
            appendChat("ASSISTANT", detail)
            speechRecognizer?.destroy()
            speechRecognizer = null
            liveChatEnabled = false
            binding.liveChatButton.text = "Canlı konuşma"
        }
    }

"""
m=m[:a]+voice+m[b:]
m=m.replace("    private fun processCommand(raw: String) {","    private fun processCommand(raw: String, forceLocalChat: Boolean = false) {",1)
old="""        memory.save(raw, "\${command.type}: \${command.description}")
        binding.resultText.text = "Algılanan komut: \${command.description}\\nİşlem: \${command.type}$correctionNotice"

        when (command.type) {"""
new="""        memory.save(raw, "\${command.type}: \${command.description}")
        binding.resultText.text = if (forceLocalChat) "Düşünüyor..." else "Algılanan komut: \${command.description}\\nİşlem: \${command.type}$correctionNotice"
        if (forceLocalChat) {
            askLocalModel(raw)
            return
        }
        when (command.type) {"""
if old not in m: raise SystemExit("process routing anchor missing")
m=m.replace(old,new,1)
m=m.replace('Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com"))','Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_APP_BROWSER)',1)
m=m.replace("binding.modelButton.isEnabled = false","setToolsModelButtonEnabled(false)")
m=m.replace("binding.modelButton.isEnabled = true","setToolsModelButtonEnabled(true)")
m=m.replace("        binding.modelStatusText.text = LocalModelStatus.describe(this)\n","",1)
anchor="    private fun installOrLoadLocalModel() {"
helpers="""    private fun autoLoadExistingLocalModel() {
        val file = File(filesDir, "models/\${ModelDownloader.MODEL_NAME}")
        modelOperationInProgress = true
        binding.statusText.text = "Model dosyası doğrulanıyor"
        binding.modelStatusText.text = "Qwen3-0.6B boyut ve SHA-256 kontrolü..."
        Thread({
            val valid = try { ModelDownloader.isValidModel(file) } catch (_: Exception) { false }
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                if (valid) {
                    binding.modelStatusText.text = "Model doğrulandı; RAM'e yükleniyor..."
                    initializeLocalModel(file)
                } else {
                    modelOperationInProgress = false
                    val state = if (file.exists()) "Model dosyası bozuk veya eksik" else "Model bulunamadı"
                    binding.modelStatusText.text = "$state. İlk kurulum için internet bağlantısıyla indirin."
                    binding.statusText.text = state
                }
            }
        }, "KizilElmaStartupModelCheck").start()
    }

    private fun setToolsModelButtonEnabled(enabled: Boolean) {
        toolsDialog?.findViewById<Button>(R.id.modelButton)?.isEnabled = enabled
    }

    private fun showToolsSheet() {
        if (toolsDialog?.isShowing == true) return
        val dialog = BottomSheetDialog(this)
        val content = layoutInflater.inflate(R.layout.sheet_tools, null, false)
        dialog.setContentView(content)
        content.findViewById<Switch>(R.id.voiceReplySwitch).apply {
            isChecked = voiceRepliesEnabled
            setOnCheckedChangeListener { _, enabled -> voiceRepliesEnabled = enabled; if (!enabled) tts?.stop() }
        }
        content.findViewById<Button>(R.id.modelButton).apply {
            isEnabled = !modelOperationInProgress
            setOnClickListener { installOrLoadLocalModel() }
        }
        content.findViewById<Button>(R.id.screenButton).setOnClickListener { requestScreenCapture(); dialog.dismiss() }
        content.findViewById<Button>(R.id.stopButton).setOnClickListener {
            ScreenCaptureService.stop(this)
            binding.statusText.text = "Ekran analizi durduruldu"
            appendChat("ASSISTANT", "Ekran analizi durduruldu.")
            dialog.dismiss()
        }
        content.findViewById<Button>(R.id.accessibilityButton).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)); dialog.dismiss()
        }
        content.findViewById<TextView>(R.id.toolsModelStatusText).text = binding.modelStatusText.text
        content.findViewById<TextView>(R.id.toolsOcrText).text = binding.ocrText.text
        toolsDialog = dialog
        dialog.setOnDismissListener { toolsDialog = null }
        dialog.show()
    }

"""
if anchor not in m: raise SystemExit("model installer anchor missing")
m=m.replace(anchor,helpers+anchor,1)
m=m.replace('''                    binding.modelStatusText.text = "Yerel LLM: Hazır (Qwen3-0.6B / CPU)"
                    speak("Yerel yapay zekâ hazır")''','''                    binding.modelStatusText.text = "Yerel LLM: Hazır · Qwen3-0.6B doğrulandı ve RAM'e yüklendi"
                    binding.statusText.text = "Çevrimdışı asistan hazır"
                    toolsDialog?.findViewById<TextView>(R.id.toolsModelStatusText)?.text = binding.modelStatusText.text''',1)
m=m.replace('''                    binding.modelStatusText.text = "Yerel model başlatılamadı: $message"''','''                    binding.modelStatusText.text = "Model yüklenemedi: $message"
                    binding.statusText.text = "Model yükleme hatası"
                    appendChat("ASSISTANT", "Hata: Model yüklenemedi - $message")''',1)
m=m.replace('''                binding.modelStatusText.text = "Model indirilemedi: $message"''','''                binding.modelStatusText.text = "Model indirilemedi: $message"
                binding.statusText.text = "Model indirilemedi"
                appendChat("ASSISTANT", "Hata: Model indirilemedi - $message")''',1)
m=m.replace('''                    binding.resultText.text = text
                    memory.appendChatMessage("ASSISTANT", text)
                    renderChatHistory()
                    speak(text.take(350))''','''                    binding.resultText.text = text
                    memory.appendChatMessage("ASSISTANT", text)
                    renderChatHistory()
                    if (liveChatEnabled) speakLiveReply(text.take(900)) else speak(text.take(350))''',1)
m=m.replace('''                    binding.resultText.text = "Yerel model hatası: $message"
                    memory.appendChatMessage("SYSTEM", "Yerel model hatası: $message")
                    renderChatHistory()''','''                    val diagnostic = "Hata: Yerel model yanıt üretemedi - $message"
                    binding.resultText.text = diagnostic
                    memory.appendChatMessage("ASSISTANT", diagnostic)
                    renderChatHistory()
                    if (liveChatEnabled) startVoiceInput()''',1)
m=m.replace('''        if (!llm.isReady()) {
            val notice = "Yerel model henüz hazır değil. Önce model indirme ve yükleme işlemini tamamlayın."
            binding.resultText.append("\\n$notice")
            appendChat("SYSTEM", notice)
            speak("Yerel yapay zekâ henüz hazır değil")
            return
        }''','''        if (!llm.isReady()) {
            val notice = "Hata: Yerel model RAM'e yüklenmedi. Durum: \${binding.modelStatusText.text}"
            binding.resultText.text = notice
            appendChat("ASSISTANT", notice)
            if (liveChatEnabled) startVoiceInput()
            return
        }''',1)
m=m.replace('''            } else {
                binding.statusText.text = "Sesli komut için mikrofon izni verilmedi; metin komutları kullanılabilir."
            }''','''            } else {
                binding.statusText.text = "Mikrofon izni verilmedi"
                appendChat("ASSISTANT", "Mikrofon izni olmadan sesli sohbet başlatılamaz.")
                liveChatEnabled = false
                binding.liveChatButton.text = "Canlı konuşma"
            }''',1)
oldT="""    private fun speak(message: String) {
        if (!voiceRepliesEnabled || message.isBlank()) return
        tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "kizil-elma-\${System.currentTimeMillis()}")
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale("tr", "TR")
        }
    }
"""
newT="""    private fun speak(message: String) {
        if (!voiceRepliesEnabled || !offlineTtsAvailable || message.isBlank()) return
        tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "kizil-elma-\${System.currentTimeMillis()}")
    }

    private fun speakLiveReply(message: String) {
        if (!liveChatEnabled) return
        if (!voiceRepliesEnabled || !offlineTtsAvailable) {
            appendChat("ASSISTANT", "Çevrimdışı Türkçe TTS bulunamadı; canlı sohbet kapatıldı.")
            liveChatEnabled = false
            binding.liveChatButton.text = "Canlı konuşma"
            return
        }
        binding.statusText.text = "Konuşuyorum..."
        val result = tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "kizil-elma-live-\${System.currentTimeMillis()}")
        if (result != TextToSpeech.SUCCESS) startVoiceInput()
    }

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) {
            offlineTtsAvailable = false
            return
        }
        val localVoice = tts?.voices?.firstOrNull { it.locale.language == "tr" && !it.isNetworkConnectionRequired }
        if (localVoice != null && tts?.setVoice(localVoice) == TextToSpeech.SUCCESS) {
            offlineTtsAvailable = true
            tts?.language = localVoice.locale
        } else {
            offlineTtsAvailable = false
            binding.statusText.text = "Çevrimdışı Türkçe TTS paketi bulunamadı"
        }
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit
            override fun onDone(utteranceId: String?) {
                runOnUiThread { if (liveChatEnabled && !isFinishing && !isDestroyed) startVoiceInput() }
            }
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                runOnUiThread {
                    if (liveChatEnabled && !isFinishing && !isDestroyed) {
                        appendChat("ASSISTANT", "Çevrimdışı sesli yanıt oynatılamadı.")
                        startVoiceInput()
                    }
                }
            }
        })
    }
"""
if oldT not in m: raise SystemExit("TTS anchor missing")
m=m.replace(oldT,newT,1)
m=m.replace('''        tts?.stop()
        tts?.shutdown()''','''        liveChatEnabled = false
        mainHandler.removeCallbacksAndMessages(null)
        speechRecognizer?.cancel()
        speechRecognizer?.destroy()
        speechRecognizer = null
        toolsDialog?.dismiss()
        tts?.stop()
        tts?.shutdown()''',1)
bubble="""                setPadding(dp(14), dp(11), dp(14), dp(11))
                maxWidth = (resources.displayMetrics.widthPixels * 0.84f).toInt()
                background = GradientDrawable().apply {
                    cornerRadius = dp(18).toFloat()
                    setColor(when {
                        isUser -> Color.rgb(38, 91, 133)
                        isSystem -> Color.rgb(65, 53, 35)
                        else -> Color.rgb(31, 45, 57)
                    })
                }
"""
bubble2="""                setPadding(dp(16), dp(13), dp(16), dp(13))
                textSize = 15.5f
                setLineSpacing(dp(3).toFloat(), 1.0f)
                maxWidth = (resources.displayMetrics.widthPixels * 0.84f).toInt()
                background = GradientDrawable().apply {
                    cornerRadius = dp(20).toFloat()
                    setColor(when {
                        isUser -> Color.rgb(14, 116, 144)
                        isSystem -> Color.rgb(71, 55, 36)
                        else -> Color.rgb(30, 41, 59)
                    })
                    setStroke(dp(1), if (isUser) Color.rgb(45, 212, 191) else Color.rgb(51, 65, 85))
                }
"""
if bubble not in m: raise SystemExit("bubble style anchor missing")
m=m.replace(bubble,bubble2,1)
M.write_text(m)
e=e.replace("activeConversation.sendMessage(safePrompt).text.trim()","activeConversation.sendMessage(safePrompt).contents.toString().trim()",1)
e=e.replace('error(callback, failure.localizedMessage ?: "Model yanıt üretemedi")','error(callback, "\${failure.javaClass.simpleName}: \${failure.localizedMessage ?: "Model yanıt üretemedi"}")',1)
E.write_text(e)
(R/"app/src/main/res/values/styles.xml").write_text("""<resources>
<style name="Theme.KizilElma" parent="Theme.Material3.Dark.NoActionBar">
<item name="colorPrimary">#38BDF8</item><item name="colorOnPrimary">#082F49</item>
<item name="colorSecondary">#2DD4BF</item><item name="colorOnSecondary">#042F2E</item>
<item name="android:colorAccent">#38BDF8</item><item name="android:windowLightStatusBar">false</item>
<item name="android:statusBarColor">#0B1220</item><item name="android:navigationBarColor">#0B1220</item>
<item name="android:windowBackground">#0B1220</item></style></resources>""")
L.write_text("""<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" xmlns:app="http://schemas.android.com/apk/res-auto"
android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:background="#0B1220" android:fitsSystemWindows="true">
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:padding="14dp" android:background="#101A2B">
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center_vertical">
<LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:orientation="vertical">
<TextView android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="KIZIL ELMA" android:textColor="#F8FAFC" android:textSize="20sp" android:textStyle="bold"/>
<TextView android:id="@+id/modelStatusText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="3dp" android:text="Model kontrol ediliyor..." android:textColor="#94A3B8" android:textSize="11sp"/>
</LinearLayout>
<com.google.android.material.button.MaterialButton android:id="@+id/liveChatButton" android:layout_width="wrap_content" android:layout_height="44dp" android:text="Canlı konuşma" android:textSize="12sp" android:textAllCaps="false" app:cornerRadius="22dp" app:backgroundTint="#0F766E" android:textColor="#ECFEFF"/>
<ImageButton android:id="@+id/settingsToggleButton" android:layout_width="44dp" android:layout_height="44dp" android:layout_marginStart="4dp" android:background="?attr/selectableItemBackgroundBorderless" android:contentDescription="Ayarlar ve araçlar" android:src="@android:drawable/ic_menu_more" android:tint="#CBD5E1"/>
</LinearLayout>
<TextView android:id="@+id/statusText" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="7dp" android:text="Çevrimdışı asistan başlatılıyor" android:textColor="#38BDF8" android:textSize="12sp"/>
</LinearLayout>
<View android:layout_width="match_parent" android:layout_height="1dp" android:background="#1E293B"/>
<ScrollView android:id="@+id/chatScrollView" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:clipToPadding="false" android:fillViewport="true">
<LinearLayout android:id="@+id/chatMessagesContainer" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:padding="16dp">
<TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center" android:padding="28dp" android:text="Merhaba. Ben Kızıl Elma. İnternetsiz yerel asistanın." android:textColor="#CBD5E1" android:textSize="16sp"/>
</LinearLayout></ScrollView>
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:padding="10dp" android:background="#101A2B">
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center_vertical" android:orientation="horizontal">
<ImageButton android:id="@+id/voiceButton" android:layout_width="48dp" android:layout_height="48dp" android:background="?attr/selectableItemBackgroundBorderless" android:contentDescription="Çevrimdışı sesle komut ver" android:src="@android:drawable/ic_btn_speak_now" android:tint="#5EEAD4"/>
<com.google.android.material.card.MaterialCardView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" app:cardBackgroundColor="#1E293B" app:cardCornerRadius="22dp" app:strokeColor="#334155" app:strokeWidth="1dp">
<EditText android:id="@+id/commandInput" android:layout_width="match_parent" android:layout_height="wrap_content" android:minHeight="50dp" android:maxLines="4" android:padding="14dp" android:background="@android:color/transparent" android:hint="Mesajını yaz..." android:inputType="textCapSentences|textMultiLine" android:textColor="#FFFFFF" android:textColorHint="#94A3B8" android:textSize="15sp"/>
</com.google.android.material.card.MaterialCardView>
<ImageButton android:id="@+id/runButton" android:layout_width="48dp" android:layout_height="48dp" android:layout_marginStart="6dp" android:background="?attr/selectableItemBackgroundBorderless" android:contentDescription="Mesajı gönder" android:src="@android:drawable/ic_menu_send" android:tint="#38BDF8"/>
</LinearLayout>
<TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center" android:layout_marginTop="6dp" android:text="Yerel Qwen3-0.6B · Ağ bağlantısı olmadan yanıt" android:textColor="#64748B" android:textSize="10sp"/>
</LinearLayout>
<TextView android:id="@+id/ocrText" android:layout_width="1dp" android:layout_height="1dp" android:visibility="gone"/>
<TextView android:id="@+id/resultText" android:layout_width="1dp" android:layout_height="1dp" android:visibility="gone"/>
</LinearLayout>""")
(R/"app/src/main/res/layout/sheet_tools.xml").write_text("""<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:padding="20dp" android:background="#111C2D">
<TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="AYARLAR VE ARAÇLAR" android:textColor="#F8FAFC" android:textSize="18sp" android:textStyle="bold" android:paddingBottom="12dp"/>
<Switch android:id="@+id/voiceReplySwitch" android:layout_width="match_parent" android:layout_height="wrap_content" android:checked="true" android:text="Yanıtları çevrimdışı sesli oku" android:textColor="#E2E8F0"/>
<com.google.android.material.button.MaterialButton android:id="@+id/modelButton" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Yerel yapay zekâyı indir / yükle" android:textAllCaps="false"/>
<TextView android:id="@+id/toolsModelStatusText" android:layout_width="match_parent" android:layout_height="wrap_content" android:padding="8dp" android:text="Model durumu" android:textColor="#94A3B8"/>
<com.google.android.material.button.MaterialButton android:id="@+id/screenButton" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Ekran analizini başlat" android:textAllCaps="false"/>
<com.google.android.material.button.MaterialButton android:id="@+id/stopButton" android:layout_width="match_parent" android:layout_height="wrap_content" style="@style/Widget.Material3.Button.OutlinedButton" android:text="Ekran analizini durdur" android:textAllCaps="false"/>
<com.google.android.material.button.MaterialButton android:id="@+id/accessibilityButton" android:layout_width="match_parent" android:layout_height="wrap_content" style="@style/Widget.Material3.Button.OutlinedButton" android:text="Erişilebilirlik iznini aç" android:textAllCaps="false"/>
<TextView android:id="@+id/toolsOcrText" android:layout_width="match_parent" android:layout_height="wrap_content" android:minHeight="32dp" android:textColor="#CBD5E1" android:paddingTop="8dp"/>
</LinearLayout>""")
manifest=A.read_text().replace('android:theme="@android:style/Theme.Material.Light.NoActionBar"','android:theme="@style/Theme.KizilElma"',1)
manifest=manifest.replace('''        <intent>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LAUNCHER" />
        </intent>''','''        <intent>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LAUNCHER" />
        </intent>
        <intent><action android:name="android.speech.RecognitionService" /></intent>''',1)
A.write_text(manifest)
g=G.read_text()
if 'versionCode = 17' not in g or 'versionName = "0.6.4"' not in g: raise SystemExit("Unexpected source baseline version")
G.write_text(g.replace('versionCode = 17','versionCode = 21',1).replace('versionName = "0.6.4"','versionName = "0.7.0"',1))
(R/"CHANGELOG_0.7.0.md").write_text("# Kızıl Elma Mobil 0.7.0\n\n- Açılışta Qwen3 modelini SHA-256 doğrulaması sonrası otomatik yükleme.\n- Yerel Android STT ve yalnızca çevrimdışı Türkçe TTS.\n- Hands-Free canlı sohbet döngüsü.\n- Material 3 koyu arayüz ve BottomSheet araçları.\n- LLM hataları asistan sohbet balonunda.\n")
assert 'SpeechRecognizer.createOnDeviceSpeechRecognizer(this)' in m
assert 'startActivityForResult(intent, speechRequest)' not in m
assert 'autoLoadExistingLocalModel()' in m and 'ModelDownloader.isValidModel(file)' in m
assert 'setOnUtteranceProgressListener' in m and 'BottomSheetDialog(this)' in m
assert 'versionCode = 21' in G.read_text() and 'versionName = "0.7.0"' in G.read_text()
assert 'EXPECTED_SHA256' in D.read_text()
for x in (L,R/"app/src/main/res/layout/sheet_tools.xml",A,R/"app/src/main/res/values/styles.xml"): ET.parse(x)
print("v0.7.0 patch applied and source sanity checks passed")

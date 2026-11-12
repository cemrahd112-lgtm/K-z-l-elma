from pathlib import Path

ROOT = Path(".")
MAIN = ROOT / "app/src/main/java/com/kizilelma/mobile/MainActivity.kt"
ENGINE = ROOT / "app/src/main/java/com/kizilelma/mobile/assistant/LocalLlmEngine.kt"
GRADLE = ROOT / "app/build.gradle.kts"

main = MAIN.read_text()
replacements = [
    ("    @Volatile private var modelOperationInProgress = false\n    private var voiceRepliesEnabled = true",
     "    @Volatile private var modelOperationInProgress = false\n    @Volatile private var pendingLocalPrompt: String? = null\n    private var voiceRepliesEnabled = true", "pending prompt state"),
    ("        binding.runButton.setOnClickListener {\n            val message = binding.commandInput.text.toString()\n            binding.commandInput.text.clear()\n            processCommand(message)\n        }\n\n    }",
     "        binding.runButton.setOnClickListener {\n            val message = binding.commandInput.text.toString()\n            binding.commandInput.text.clear()\n            processCommand(message)\n        }\n\n        // Load a previously downloaded local model automatically; never download it silently.\n        loadExistingLocalModelIfPresent()\n    }", "startup model initialization"),
    ('            key.contains("tarayıcı") || key.contains("internet") || key == "chrome" ->\n                Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com"))',
     '            key.contains("tarayıcı") || key.contains("internet") || key == "chrome" ->\n                Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_APP_BROWSER)', "remove Google URL fallback"),
]
for old, new, label in replacements:
    if old not in main:
        raise SystemExit(f"MainActivity patch anchor missing: {label}")
    main = main.replace(old, new, 1)

anchor = "    private fun installOrLoadLocalModel() {"
loader = '''    private fun loadExistingLocalModelIfPresent() {
        val modelFile = File(filesDir, "models/${ModelDownloader.MODEL_NAME}")
        if (!modelFile.isFile || modelOperationInProgress) return
        modelOperationInProgress = true
        binding.modelButton.isEnabled = false
        binding.modelStatusText.text = "Mevcut yerel model doğrulanıyor..."
        Thread({
            val valid = try { ModelDownloader.isValidModel(modelFile) } catch (_: Exception) { false }
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                if (valid) {
                    initializeLocalModel(modelFile)
                } else {
                    modelOperationInProgress = false
                    binding.modelButton.isEnabled = true
                    val notice = "Yerel model dosyası geçersiz. Modeli yeniden indirmeniz gerekiyor."
                    binding.modelStatusText.text = notice
                    if (!pendingLocalPrompt.isNullOrBlank()) {
                        pendingLocalPrompt = null
                        binding.resultText.text = notice
                        appendChat("SYSTEM", notice)
                    }
                }
            }
        }, "KizilElmaAutoModelLoad").start()
    }

'''
if anchor not in main:
    raise SystemExit("MainActivity patch anchor missing: installOrLoadLocalModel")
main = main.replace(anchor, loader + anchor, 1)
main = main.replace(
    '    private fun initializeLocalModel(modelFile: File) {\n        binding.modelButton.isEnabled = false',
    '    private fun initializeLocalModel(modelFile: File) {\n        modelOperationInProgress = true\n        binding.modelButton.isEnabled = false', 1)
main = main.replace(
    '                    modelOperationInProgress = false\n                    binding.modelButton.isEnabled = true\n                    binding.modelStatusText.text = "Yerel LLM: Hazır (Qwen3-0.6B / CPU)"\n                    speak("Yerel yapay zekâ hazır")',
    '                    modelOperationInProgress = false\n                    binding.modelButton.isEnabled = true\n                    binding.modelStatusText.text = "Yerel LLM: Hazır (Qwen3-0.6B / CPU)"\n                    speak("Yerel yapay zekâ hazır")\n                    val queuedPrompt = pendingLocalPrompt\n                    pendingLocalPrompt = null\n                    if (!queuedPrompt.isNullOrBlank()) askLocalModelNow(queuedPrompt)', 1)
main = main.replace(
    '                    modelOperationInProgress = false\n                    binding.modelButton.isEnabled = true\n                    binding.modelStatusText.text = "Yerel model başlatılamadı: $message"',
    '                    modelOperationInProgress = false\n                    pendingLocalPrompt = null\n                    binding.modelButton.isEnabled = true\n                    binding.modelStatusText.text = "Yerel model başlatılamadı: $message"\n                    binding.resultText.text = "Yerel model başlatılamadı: $message"', 1)
main = main.replace(
    '                modelOperationInProgress = false\n                binding.modelButton.isEnabled = true\n                binding.modelStatusText.text = "Model indirilemedi: $message"',
    '                modelOperationInProgress = false\n                pendingLocalPrompt = null\n                binding.modelButton.isEnabled = true\n                binding.modelStatusText.text = "Model indirilemedi: $message"\n                binding.resultText.text = "Yerel model indirilemedi: $message"', 1)

old_ask = '''    private fun askLocalModel(userText: String) {
        if (!llm.isReady()) {
            val notice = "Yerel model henüz hazır değil. Önce model indirme ve yükleme işlemini tamamlayın."
            binding.resultText.append("\\n$notice")
            appendChat("SYSTEM", notice)
            speak("Yerel yapay zekâ henüz hazır değil")
            return
        }

        // Keep untrusted context bounded so the final safety rules are never cut off by the engine limit.'''
new_ask = '''    private fun askLocalModel(userText: String) {
        if (!llm.isReady()) {
            pendingLocalPrompt = userText
            if (modelOperationInProgress) {
                binding.resultText.text = "Yerel model hazırlanıyor. Mesajınız hazır olduğunda işlenecek."
                binding.modelStatusText.text = "Yerel model yükleniyor; mesaj sıraya alındı."
                return
            }
            val modelFile = File(filesDir, "models/${ModelDownloader.MODEL_NAME}")
            if (!modelFile.isFile) {
                pendingLocalPrompt = null
                val notice = "Qwen3-0.6B yerel modeli henüz indirilmemiş. Yerel yanıt için modeli indir/yükle düğmesini kullanın."
                binding.resultText.text = notice
                appendChat("SYSTEM", notice)
                speak("Yerel model henüz indirilmedi")
                return
            }
            modelOperationInProgress = true
            binding.modelStatusText.text = "Yerel model doğrulanıyor ve başlatılıyor..."
            binding.resultText.text = "Yerel model başlatılıyor. Mesajınız sıraya alındı."
            Thread({
                val valid = try { ModelDownloader.isValidModel(modelFile) } catch (_: Exception) { false }
                runOnUiThread {
                    if (isFinishing || isDestroyed) return@runOnUiThread
                    if (valid) {
                        initializeLocalModel(modelFile)
                    } else {
                        modelOperationInProgress = false
                        pendingLocalPrompt = null
                        val notice = "Yerel model dosyası eksik veya bozuk. Modeli indir/yükle düğmesiyle yeniden indirin."
                        binding.resultText.text = notice
                        binding.modelStatusText.text = notice
                        appendChat("SYSTEM", notice)
                    }
                }
            }, "KizilElmaPromptModelLoad").start()
            return
        }
        askLocalModelNow(userText)
    }

    private fun askLocalModelNow(userText: String) {
        if (!llm.isReady()) {
            binding.resultText.text = "Yerel model hazır değil; istek gönderilmedi."
            return
        }

        // Keep untrusted context bounded so the final safety rules are never cut off by the engine limit.'''
if old_ask not in main:
    raise SystemExit("MainActivity patch anchor missing: askLocalModel")
main = main.replace(old_ask, new_ask, 1)
MAIN.write_text(main)

engine = ENGINE.read_text()
old_responses = [
    'activeConversation.sendMessage(safePrompt).text.trim()',
    'activeConversation.sendMessage(safePrompt).toString().trim()',
]
new_response = 'activeConversation.sendMessage(safePrompt).contents.toString().trim()'
if new_response not in engine:
    matched = next((item for item in old_responses if item in engine), None)
    if matched is None:
        raise SystemExit("LocalLlmEngine response extraction anchor missing")
    engine = engine.replace(matched, new_response, 1)
ENGINE.write_text(engine)

gradle = GRADLE.read_text()
if 'versionCode = 17' in gradle and 'versionName = "0.6.4"' in gradle:
    gradle = gradle.replace('versionCode = 17', 'versionCode = 19', 1)
    gradle = gradle.replace('versionName = "0.6.4"', 'versionName = "0.6.6"', 1)
elif 'versionCode = 18' in gradle and 'versionName = "0.6.5"' in gradle:
    gradle = gradle.replace('versionCode = 18', 'versionCode = 19', 1)
    gradle = gradle.replace('versionName = "0.6.5"', 'versionName = "0.6.6"', 1)
else:
    raise SystemExit("Expected v0.6.4 or v0.6.5 version fields were not found")
GRADLE.write_text(gradle)
print("Applied Kızıl Elma v0.6.6 local-LLM routing patch and version 19.")

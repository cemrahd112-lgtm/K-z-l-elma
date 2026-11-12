from pathlib import Path
import xml.etree.ElementTree as ET
R = Path(".")
M = R / "app/src/main/java/com/kizilelma/mobile/MainActivity.kt"
G = R / "app/build.gradle.kts"
m = M.read_text()
g = G.read_text()
if 'versionCode = 24' not in g or 'versionName = "0.7.3"' not in g:
    raise SystemExit("Unexpected pre-v0.7.5 Gradle version")
G.write_text(g.replace('versionCode = 24', 'versionCode = 26', 1).replace('versionName = "0.7.3"', 'versionName = "0.7.5"', 1))
old_missing = 'binding.modelStatusText.text = "$state. İlk kurulum için internet bağlantısıyla indirin."'
new_missing = 'binding.modelStatusText.text = "$state. Gömülü model bulunmuyor; çevrimdışı sohbet için Ayarlar > Yerel yapay zekâyı indir / yükle bölümünden modeli bir kez kurun. Kurulumdan sonra internet gerekmez."'
if old_missing not in m: raise SystemExit("Missing-model status anchor not found")
m = m.replace(old_missing, new_missing, 1)
m = m.replace('binding.modelStatusText.text = "Qwen3-0.6B boyut ve SHA-256 kontrolü..."', 'binding.modelStatusText.text = "Yerel model kontrol ediliyor; açılışta ağ bağlantısı kullanılmaz..."', 1)
m = m.replace('android:text="Yerel yapay zekâyı indir / yükle"', 'android:text="Yerel yapay zekâyı bir kez indir / yükle"', 1)
m = m.replace('findViewById<Button>(R.id.modelButton).apply {', 'findViewById<Button>(R.id.modelButton).apply {\n            text = "Yerel yapay zekâyı bir kez indir / yükle"', 1)
old_results = '''                            binding.commandInput.setText(spoken)
                            binding.commandInput.setSelection(spoken.length)
                            processCommand(spoken, forceLocalChat = liveChatEnabled)'''
new_results = '''                            binding.commandInput.text?.clear()
                            appendChat("USER", spoken)
                            processCommand(spoken, forceLocalChat = liveChatEnabled)'''
if old_results not in m: raise SystemExit("Speech final-results UI anchor not found")
m = m.replace(old_results, new_results, 1)
old_partial = '''                        if (partial.isNotBlank()) runOnUiThread { if (!isFinishing && !isDestroyed) binding.commandInput.setText(partial) }'''
new_partial = '''                        if (partial.isNotBlank()) runOnUiThread {
                            if (!isFinishing && !isDestroyed && liveChatEnabled) {
                                binding.statusText.text = "Konuşma algılanıyor..."
                            }
                        }'''
if old_partial not in m: raise SystemExit("Speech partial-results anchor not found")
m = m.replace(old_partial, new_partial, 1)
m = m.replace(
    'val detail = "Çevrimdışı ses tanıma başlatılamadı. Lütfen cihaz ayarlarından çevrimdışı Türkçe dil paketini indirin. Ayrıntı: \${failure.localizedMessage ?: failure.javaClass.simpleName}"',
    'val detail = "Çevrimdışı ses tanıma başlatılamadı. Türkçe çevrimdışı dil paketi veya cihazın yerel tanıma servisi kullanılamıyor. Metin girişine dönüldü. Ayrıntı: \${failure.localizedMessage ?: failure.javaClass.simpleName}"',
    1
)
needle = '''                                if (liveChatEnabled) {
                                    liveChatEnabled = false
                                    updateAutonomousButtonState()
                                    stopAutonomousForegroundSession()
                                }'''
replacement = '''                                if (liveChatEnabled) {
                                    liveChatEnabled = false
                                    updateAutonomousButtonState()
                                    stopAutonomousForegroundSession()
                                    try { tts?.stop() } catch (_: Exception) { }
                                }
                                try { speechRecognizer?.cancel() } catch (_: Exception) { }
                                try { speechRecognizer?.destroy() } catch (_: Exception) { }
                                speechRecognizer = null
                                binding.commandInput.text?.clear()
                                binding.statusText.text = "Sesli mod kapalı · Metin girişi kullanılabilir"'''
if needle not in m: raise SystemExit("Terminal STT error cleanup anchor not found")
m = m.replace(needle, replacement, 1)
old_tts_error = '''                        appendChat("ASSISTANT", "Çevrimdışı sesli yanıt oynatılamadı.")
                        startVoiceInput()'''
new_tts_error = '''                        appendChat("ASSISTANT", "Çevrimdışı sesli yanıt oynatılamadı; dinleme yeniden başlatılıyor.")
                        try { tts?.stop() } catch (_: Exception) { }
                        startVoiceInput()'''
if old_tts_error not in m: raise SystemExit("TTS error recovery anchor not found")
m = m.replace(old_tts_error, new_tts_error, 1)
if 'override fun onDone(utteranceId: String?)' not in m or 'startVoiceInput()' not in m:
    raise SystemExit("Autonomous STT -> LLM -> TTS loop anchors missing")
M.write_text(m)
(R / "CHANGELOG_0.7.5.md").write_text(
    "# Kızıl Elma Mobil 0.7.5\n\n"
    "- Version Code 26.\n"
    "- Açılışta model kontrolü tamamen yereldir; otomatik ağ indirmesi yapılmaz.\n"
    "- Model dosyası yoksa çevrimdışı LLM'nin henüz hazır olmadığı açıkça belirtilir ve tek seferlik kurulum yolu gösterilir.\n"
    "- STT ara sonuçları komut alanını kirletmez; tamamlanan konuşma sohbet geçmişine yazılır ve bir kez işlenir.\n"
    "- STT hata/istisna durumlarında tanıyıcı ve otonom servis temizlenir; metin girişi kullanılabilir kalır.\n"
    "- TTS hata kurtarması dinleme döngüsünü kontrollü biçimde yeniden başlatır.\n"
)
assert 'versionCode = 26' in G.read_text() and 'versionName = "0.7.5"' in G.read_text()
assert 'binding.commandInput.setText(spoken)' not in m
assert 'appendChat("USER", spoken)' in m
assert 'Konuşma algılanıyor...' in m
assert 'Gömülü model bulunmuyor' in m
print("v0.7.5 patch applied; version, STT, TTS, and model fallback assertions passed")

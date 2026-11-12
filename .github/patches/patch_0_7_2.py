from pathlib import Path
R = Path(".")
M = R / "app/src/main/java/com/kizilelma/mobile/MainActivity.kt"
L = R / "app/src/main/res/layout/activity_main.xml"
G = R / "app/build.gradle.kts"
m = M.read_text()
layout = L.read_text()
gradle = G.read_text()

# The existing live-chat control becomes the dedicated autonomous mode switch.
layout = layout.replace('android:text="Canlı konuşma"', 'android:text="Otonom Sohbet"', 1)
m = m.replace('''        binding.liveChatButton.setOnClickListener { toggleLiveChat() }
''', '''        binding.liveChatButton.setOnClickListener { toggleLiveChat() }
        updateAutonomousButtonState()
''', 1)

old_toggle = '''    private fun toggleLiveChat() {
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
'''
new_toggle = '''    private fun updateAutonomousButtonState() {
        binding.liveChatButton.text = if (liveChatEnabled) "Otonom Sohbet · Açık" else "Otonom Sohbet"
        val activeColor = android.graphics.Color.rgb(20, 184, 166)
        val inactiveColor = android.graphics.Color.rgb(51, 65, 85)
        binding.liveChatButton.backgroundTintList =
            android.content.res.ColorStateList.valueOf(if (liveChatEnabled) activeColor else inactiveColor)
    }

    private fun toggleLiveChat() {
        liveChatEnabled = !liveChatEnabled
        updateAutonomousButtonState()
        if (liveChatEnabled) {
            binding.statusText.text = "Otonom sohbet aktif · Dinliyorum"
            startVoiceInput()
        } else {
            speechRecognizer?.cancel()
            tts?.stop()
            binding.statusText.text = "Otonom sohbet kapalı"
        }
    }
'''
if old_toggle not in m:
    raise SystemExit("Autonomous toggle insertion anchor missing")
m = m.replace(old_toggle, new_toggle, 1)

# Keep the visible control state synchronized after any failure path that disables the loop.
m = m.replace('binding.liveChatButton.text = "Canlı konuşma"', 'updateAutonomousButtonState()')
m = m.replace('binding.liveChatButton.text = "Canlı sohbeti bitir"', 'updateAutonomousButtonState()')
m = m.replace('''        if (forceLocalChat) {
            askLocalModel(raw)
            return
        }
''', '''        if (forceLocalChat) {
            binding.statusText.text = "Kendi kendine düşünüyor..."
            askLocalModel(raw)
            return
        }
''', 1)

m = m.replace('binding.statusText.text = "Düşünüyor..."', 'binding.statusText.text = "Kendi kendine düşünüyor..."')

# Ensure autonomous mode is still enabled before the TTS completion callback restarts listening.
old_done = '''            override fun onDone(utteranceId: String?) {
                runOnUiThread { if (liveChatEnabled && !isFinishing && !isDestroyed) startVoiceInput() }
            }
'''
new_done = '''            override fun onDone(utteranceId: String?) {
                runOnUiThread {
                    if (liveChatEnabled && !isFinishing && !isDestroyed) {
                        binding.statusText.text = "Otonom sohbet · Yeniden dinleniyor"
                        startVoiceInput()
                    }
                }
            }
'''
if old_done not in m:
    raise SystemExit("TTS onDone callback anchor missing")
m = m.replace(old_done, new_done, 1)

# The LLM request is the autonomous reasoning phase.
m = m.replace('binding.statusText.text = "Düşünüyor..."', 'binding.statusText.text = "Kendi kendine düşünüyor..."')
M.write_text(m)
L.write_text(layout)

if 'versionCode = 22' not in gradle or 'versionName = "0.7.1"' not in gradle:
    raise SystemExit("Unexpected pre-v0.7.2 Gradle version")
G.write_text(gradle.replace('versionCode = 22', 'versionCode = 23', 1).replace('versionName = "0.7.1"', 'versionName = "0.7.2"', 1))

(R / "CHANGELOG_0.7.2.md").write_text(
    "# Kızıl Elma Mobil 0.7.2\\n\\n"
    "- Ana ekrana özel Otonom Sohbet aç/kapat düğmesi.\\n"
    "- Aktif/pasif durumları farklı Material 3 renkleriyle gösterilir.\\n"
    "- Ses tanıma → yerel Qwen3 düşünme → çevrimdışı TTS → onDone ile otomatik dinlemeye dönüş döngüsü.\\n"
    "- Mevcut 192 token sınırı ve v0.7.1 güvenli ses hatası yönetimi korunur.\\n"
)
assert 'versionCode = 23' in G.read_text() and 'versionName = "0.7.2"' in G.read_text()
assert 'Otonom Sohbet · Açık' in m
assert 'Kendi kendine düşünüyor...' in m
assert 'if (liveChatEnabled && !isFinishing && !isDestroyed)' in m
assert 'startVoiceInput()' in m
print("v0.7.2 autonomous chat patch applied; assertions passed")

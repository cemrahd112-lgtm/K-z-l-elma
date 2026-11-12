# Kızıl Elma Mobil 1.0

Fresh Android application based on PocketPal AI's local-first separation of UI, native inference bridge and on-device engines.

## Runtime privacy
- No INTERNET or ACCESS_NETWORK_STATE permission. Manifest merger removal directives block those permissions if a dependency adds them.
- GGUF and Vosk model files are imported from local device storage. The app has no model downloader, cloud endpoint, analytics SDK or remote API client.
- Chat history is stored in app-private SQLite.
- llama.cpp performs GGUF inference through JNI.
- Speech recognition uses Vosk local model files. Android TextToSpeech is accepted only when the device exposes a Turkish voice whose `isNetworkConnectionRequired` flag is false; otherwise voice output is disabled.

## Important
This APK is an offline-capable shell, not a preloaded model bundle. GGUF and Vosk model data must be supplied locally (for example by USB). The first microphone permission prompt is required by Android. Continuous microphone use is limited to the foreground activity; Android may stop it when the app is backgrounded or the process is killed. TTS availability is device-dependent. No software can promise zero data leakage without a device/runtime audit.

## Build
GitHub Actions downloads llama.cpp source at build time and compiles the native arm64 library. This build-time source fetch is performed by CI; the installed APK has no network permission.

CI build workflow: `.github/workflows/kizil-elma-v1.yml`.

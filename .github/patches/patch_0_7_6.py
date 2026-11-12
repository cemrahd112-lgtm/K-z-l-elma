from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(".")
manifest_path = ROOT / "app/src/main/AndroidManifest.xml"
gradle_path = ROOT / "app/build.gradle.kts"
manifest = ET.parse(manifest_path)
root = manifest.getroot()

ANDROID = "{http://schemas.android.com/apk/res/android}"
TOOLS = "{http://schemas.android.com/tools}"
ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
ET.register_namespace("tools", "http://schemas.android.com/tools")

blocked = {
    "android.permission.INTERNET",
    "android.permission.ACCESS_NETWORK_STATE",
}
for child in list(root):
    if child.tag in {"uses-permission", "uses-permission-sdk-23", "uses-permission-sdk-m"}:
        name = child.get(ANDROID + "name")
        if name in blocked:
            root.remove(child)

# tools:node=remove also blocks permissions contributed by transitive library manifests.
existing = {
    (node.tag, node.get(ANDROID + "name"))
    for node in root
    if node.tag in {"uses-permission", "uses-permission-sdk-23", "uses-permission-sdk-m"}
}
for permission in sorted(blocked):
    if ("uses-permission", permission) not in existing:
        node = ET.Element("uses-permission")
        node.set(ANDROID + "name", permission)
        node.set(TOOLS + "node", "remove")
        root.insert(0, node)

manifest.write(manifest_path, encoding="utf-8", xml_declaration=True)
xml_text = manifest_path.read_text()
if "tools:" not in xml_text or "node=\"remove\"" not in xml_text:
    raise SystemExit("Manifest merge-removal directives were not written")
for permission in blocked:
    if permission not in xml_text:
        raise SystemExit("Missing manifest removal directive: " + permission)

g = gradle_path.read_text()
if 'versionCode = 26' not in g or 'versionName = "0.7.5"' not in g:
    raise SystemExit("Unexpected Gradle version; expected v0.7.5 / code 26")
g = g.replace('versionCode = 26', 'versionCode = 27', 1)
g = g.replace('versionName = "0.7.5"', 'versionName = "0.7.6"', 1)
gradle_path.write_text(g)

# Permission absence is the primary Android sandbox network barrier. Audit app-owned
# source for obvious HTTP clients and hard-coded remote API endpoints; do not scan
# dependency caches or generated build output.
source_roots = [ROOT / "app/src/main"]
patterns = [
    re.compile(r'\\b(?:OkHttpClient|Retrofit|HttpURLConnection|URL\\s*\\()'),
    re.compile(r'\\b(?:Ktor\\s*\\(|CronetEngine|WebSocket)'),
    re.compile(r'https?://', re.IGNORECASE),
]
matches = []
for source_root in source_roots:
    for path in source_root.rglob("*"):
        if path.suffix.lower() not in {".kt", ".java", ".xml"}:
            continue
        content = path.read_text(errors="replace")
        for number, line in enumerate(content.splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns):
                matches.append(f"{path}:{number}:{line.strip()}")
if matches:
    print("NOTICE: remote/network-related source patterns remain; INTERNET permission is blocked:")
    print("\\n".join(matches[:80]))

(ROOT / "CHANGELOG_0.7.6.md").write_text(
    "# Kızıl Elma Mobil 0.7.6\\n\\n"
    "- Version Code 27.\\n"
    "- INTERNET and ACCESS_NETWORK_STATE are removed from the app manifest and marked for removal during manifest merging.\\n"
    "- The Android app sandbox therefore cannot use ordinary network sockets; model downloads and remote API access are unavailable.\\n"
    "- Existing STT/TTS exception recovery from v0.7.5 is retained; Android system speech-service behavior remains device/service dependent.\\n"
    "- This build does not embed a local LLM or offline Turkish STT/TTS model.\\n"
)
assert 'versionCode = 27' in gradle_path.read_text()
assert 'versionName = "0.7.6"' in gradle_path.read_text()
print("v0.7.6 offline-permission patch applied; manifest directives and version assertions passed")

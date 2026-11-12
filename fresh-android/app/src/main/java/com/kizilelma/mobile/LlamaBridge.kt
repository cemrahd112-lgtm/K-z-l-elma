package com.kizilelma.mobile

object LlamaBridge {
    init { System.loadLibrary("kizil_llama") }
    external fun loadModel(path: String, contextSize: Int): Boolean
    external fun generate(prompt: String, maxTokens: Int): String
    external fun unload()
}

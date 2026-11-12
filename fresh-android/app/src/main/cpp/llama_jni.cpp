#include <jni.h>
#include <string>
#include <vector>
#include <mutex>
#include "llama.h"

static llama_model* model = nullptr;
static llama_context* ctx = nullptr;
static std::mutex guard;

extern "C" JNIEXPORT jboolean JNICALL
Java_com_kizilelma_mobile_LlamaBridge_loadModel(JNIEnv* env, jobject, jstring path, jint contextSize) {
    std::lock_guard<std::mutex> lock(guard);
    if (ctx) { llama_free(ctx); ctx = nullptr; }
    if (model) { llama_model_free(model); model = nullptr; }
    const char* p = env->GetStringUTFChars(path, nullptr);
    auto mp = llama_model_default_params();
    model = llama_model_load_from_file(p, mp);
    env->ReleaseStringUTFChars(path, p);
    if (!model) return JNI_FALSE;
    auto cp = llama_context_default_params();
    cp.n_ctx = (uint32_t)contextSize;
    ctx = llama_init_from_model(model, cp);
    if (!ctx) { llama_model_free(model); model = nullptr; return JNI_FALSE; }
    return JNI_TRUE;
}
extern "C" JNIEXPORT jstring JNICALL
Java_com_kizilelma_mobile_LlamaBridge_generate(JNIEnv* env, jobject, jstring input, jint maxTokens) {
    std::lock_guard<std::mutex> lock(guard);
    if (!model || !ctx) return env->NewStringUTF("Yerel GGUF modeli yüklenmedi.");
    const char* p = env->GetStringUTFChars(input, nullptr);
    std::string prompt(p); env->ReleaseStringUTFChars(input, p);
    const auto vocab = llama_model_get_vocab(model);
    std::vector<llama_token> tokens(prompt.size() + 16);
    int n = llama_tokenize(vocab, prompt.c_str(), (int)prompt.size(), tokens.data(), (int)tokens.size(), true, true);
    if (n < 0) return env->NewStringUTF("İstem çok uzun.");
    tokens.resize(n);
    llama_batch batch = llama_batch_get_one(tokens.data(), (int)tokens.size());
    if (llama_decode(ctx, batch) != 0) return env->NewStringUTF("Model değerlendirme hatası.");
    auto sampler = llama_sampler_chain_init(llama_sampler_chain_default_params());
    llama_sampler_chain_add(sampler, llama_sampler_init_greedy());
    std::string out;
    for (int i=0; i<maxTokens; ++i) {
        llama_token id = llama_sampler_sample(sampler, ctx, -1);
        if (llama_vocab_is_eog(vocab, id)) break;
        char piece[512];
        int len = llama_token_to_piece(vocab, id, piece, sizeof(piece), 0, true);
        if (len > 0) out.append(piece, len);
        batch = llama_batch_get_one(&id, 1);
        if (llama_decode(ctx, batch) != 0) break;
    }
    llama_sampler_free(sampler);
    return env->NewStringUTF(out.c_str());
}
extern "C" JNIEXPORT void JNICALL
Java_com_kizilelma_mobile_LlamaBridge_unload(JNIEnv*, jobject) {
    std::lock_guard<std::mutex> lock(guard);
    if (ctx) { llama_free(ctx); ctx = nullptr; }
    if (model) { llama_model_free(model); model = nullptr; }
}

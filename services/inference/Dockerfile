# Inference service — OpenAI-compatible vLLM server. THE model-swap boundary (§8).
#
# Tag mirrors the Leonardo onboarding slide (vllm/vllm-openai:0.21.0-cu129);
# cu129 = CUDA 12.9, which covers Blackwell (sm_120 / the RTX 5070 Ti). Using the
# same image locally and on the cluster keeps behaviour consistent.
#
# Verify this tag exists / works on your driver: `docker run --rm <image> --help`.
# If it doesn't, swap to a current vllm/vllm-openai tag built on CUDA >= 12.8.
FROM vllm/vllm-openai:0.21.0-cu129

# `vllm serve` takes the model + flags as args (supplied by docker-compose `command`).
ENTRYPOINT ["vllm", "serve"]

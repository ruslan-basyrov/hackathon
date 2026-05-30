# Inference service — OpenAI-compatible vLLM server. THE model-swap boundary (§8).
#
# cu129 = CUDA 12.9, which covers Blackwell (sm_120 / the RTX 5070 Ti). Verify
# the tag exists on Docker Hub before pinning a new one:
#   curl -s "https://hub.docker.com/v2/repositories/vllm/vllm-openai/tags/?page_size=20&ordering=last_updated"
# If a tag stops working on your driver, bump to a newer cu129 build.
FROM vllm/vllm-openai:v0.22.0-cu129-ubuntu2404

# `vllm serve` takes the model + flags as args (supplied by docker-compose `command`).
ENTRYPOINT ["vllm", "serve"]

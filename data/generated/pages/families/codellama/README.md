# codellama

codellama 5.9M Downloads Updated 2 years ago A large language model that can use text prompts to generate and discuss code. A large language model that can use text prompts to generate and discuss code. Cancel 7b 13b 34b 70b CLI cURL Python JavaScript Documentation Documentation ollama run codellama curl http://localhost:11434/api/chat \
  -d '{
    "model": "codellama",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'codellama' 

- Models: 4
- Tags: 199
- Capabilities: text_generation (203)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
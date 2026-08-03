# wizardlm

wizardlm 873.4K Downloads Updated 2 years ago General use model based on Llama 2. General use model based on Llama 2. Cancel CLI cURL Python JavaScript Documentation Documentation ollama run wizardlm:7b-q2_K curl http://localhost:11434/api/chat \
  -d '{
    "model": "wizardlm:7b-q2_K",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'wizardlm:7b-q2_K' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.

- Models: 4
- Tags: 73
- Capabilities: text_generation (77)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
# mistral

mistral 31.5M Downloads Updated 1 year ago The 7B model released by Mistral AI, updated to version 0.3. The 7B model released by Mistral AI, updated to version 0.3. Cancel tools 7b CLI cURL Python JavaScript Documentation Documentation ollama run mistral curl http://localhost:11434/api/chat \
  -d '{
    "model": "mistral",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'mistral' ,
    messages=[{ 'role' : 'user' , 'content' : 'H

- Models: 1
- Tags: 84
- Capabilities: text_generation (85), tool_use (85)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
# smollm

CLI cURL Python JavaScript Documentation Documentation ollama run smollm curl http://localhost:11434/api/chat \
  -d '{
    "model": "smollm",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'smollm' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'smollm' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})

- Models: 3
- Tags: 94
- Capabilities: text_generation (97)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
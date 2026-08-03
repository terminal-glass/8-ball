# llama4

CLI cURL Python JavaScript Documentation Documentation ollama run llama4 curl http://localhost:11434/api/chat \
  -d '{
    "model": "llama4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'llama4' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'llama4' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})

- Models: 1
- Tags: 11
- Capabilities: text_generation (12), tool_use (12), vision (12)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
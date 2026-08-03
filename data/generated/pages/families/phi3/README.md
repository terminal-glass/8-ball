# phi3

CLI cURL Python JavaScript Documentation Documentation ollama run phi3 curl http://localhost:11434/api/chat \
  -d '{
    "model": "phi3",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'phi3' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'phi3' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})
console

- Models: 2
- Tags: 72
- Capabilities: text_generation (74)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
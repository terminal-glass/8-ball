# phi4

CLI cURL Python JavaScript Documentation Documentation ollama run phi4 curl http://localhost:11434/api/chat \
  -d '{
    "model": "phi4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'phi4' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'phi4' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})
console

- Models: 1
- Tags: 5
- Capabilities: text_generation (6)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
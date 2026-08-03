# glm4

CLI cURL Python JavaScript Documentation Documentation ollama run glm4 curl http://localhost:11434/api/chat \
  -d '{
    "model": "glm4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'glm4' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'glm4' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})
console

- Models: 1
- Tags: 32
- Capabilities: text_generation (33)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
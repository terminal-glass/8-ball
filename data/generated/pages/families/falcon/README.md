# falcon

CLI cURL Python JavaScript Documentation Documentation ollama run falcon curl http://localhost:11434/api/chat \
  -d '{
    "model": "falcon",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'falcon' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'falcon' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})

- Models: 3
- Tags: 38
- Capabilities: text_generation (41)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
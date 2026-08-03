# notux

CLI cURL Python JavaScript Documentation Documentation ollama run notux curl http://localhost:11434/api/chat \
  -d '{
    "model": "notux",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'notux' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'notux' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})
con

- Models: 1
- Tags: 18
- Capabilities: text_generation (19)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
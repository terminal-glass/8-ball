# xwinlm

CLI cURL Python JavaScript Documentation Documentation ollama run xwinlm curl http://localhost:11434/api/chat \
  -d '{
    "model": "xwinlm",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'xwinlm' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'xwinlm' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})

- Models: 3
- Tags: 80
- Capabilities: text_generation (83)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
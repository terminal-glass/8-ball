# llama2

CLI cURL Python JavaScript Documentation Documentation ollama run llama2 curl http://localhost:11434/api/chat \
  -d '{
    "model": "llama2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'llama2' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'llama2' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})

- Models: 3
- Tags: 102
- Capabilities: text_generation (105)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
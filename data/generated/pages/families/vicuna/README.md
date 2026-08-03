# vicuna

CLI cURL Python JavaScript Documentation Documentation ollama run vicuna curl http://localhost:11434/api/chat \
  -d '{
    "model": "vicuna",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'vicuna' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'vicuna' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})

- Models: 3
- Tags: 111
- Capabilities: text_generation (114)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
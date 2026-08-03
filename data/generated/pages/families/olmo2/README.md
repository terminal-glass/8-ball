# olmo2

CLI cURL Python JavaScript Documentation Documentation ollama run olmo2 curl http://localhost:11434/api/chat \
  -d '{
    "model": "olmo2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'olmo2' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.content) import ollama from 'ollama' const response = await ollama.chat({
  model: 'olmo2' ,
  messages: [{role: 'user' , content: 'Hello!' }],
})
con

- Models: 2
- Tags: 9
- Capabilities: text_generation (11)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
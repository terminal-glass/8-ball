# llama3.2

llama3.2 78.6M Downloads Updated 1 year ago Meta's Llama 3.2 goes small with 1B and 3B models. Meta's Llama 3.2 goes small with 1B and 3B models. Cancel tools 1b 3b CLI cURL Python JavaScript Documentation Documentation ollama run llama3.2 curl http://localhost:11434/api/chat \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'llama3.2' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) 

- Models: 2
- Tags: 63
- Capabilities: text_generation (65), tool_use (65)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
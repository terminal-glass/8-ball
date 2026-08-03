# codeup

codeup 577.8K Downloads Updated 2 years ago Great code generation model based on Llama2. Great code generation model based on Llama2. Cancel 13b CLI cURL Python JavaScript Documentation Documentation ollama run codeup curl http://localhost:11434/api/chat \
  -d '{
    "model": "codeup",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'codeup' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.message.co

- Models: 1
- Tags: 19
- Capabilities: text_generation (20)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
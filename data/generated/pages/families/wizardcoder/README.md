# wizardcoder

wizardcoder 1M Downloads Updated 2 years ago State-of-the-art code generation model State-of-the-art code generation model Cancel 33b CLI cURL Python JavaScript Documentation Documentation ollama run wizardcoder curl http://localhost:11434/api/chat \
  -d '{
    "model": "wizardcoder",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'wizardcoder' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (response.messag

- Models: 4
- Tags: 67
- Capabilities: text_generation (71)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
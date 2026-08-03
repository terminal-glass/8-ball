# wizard-math

wizard-math 993.8K Downloads Updated 2 years ago Model focused on math and logic problems Model focused on math and logic problems Cancel 7b 13b 70b CLI cURL Python JavaScript Documentation Documentation ollama run wizard-math curl http://localhost:11434/api/chat \
  -d '{
    "model": "wizard-math",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'wizard-math' ,
    messages=[{ 'role' : 'user' , 'content' : 'Hello!' }],
) print (

- Models: 3
- Tags: 64
- Capabilities: text_generation (67)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
# notus

notus 526.8K Downloads Updated 2 years ago A 7B chat model fine-tuned with high-quality data and based on Zephyr. A 7B chat model fine-tuned with high-quality data and based on Zephyr. Cancel 7b CLI cURL Python JavaScript Documentation Documentation ollama run notus curl http://localhost:11434/api/chat \
  -d '{
    "model": "notus",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' from ollama import chat

response = chat(
    model= 'notus' ,
    messages=[{ 'role' : 'user' , 'conte

- Models: 1
- Tags: 18
- Capabilities: text_generation (19)

Deployment coverage is summarized per model under `data/generated/pages/models/`.
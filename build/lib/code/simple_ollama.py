from litellm import completion

response = completion(
    model="ollama/qwen2.5-coder:latest",
    messages=[{"content": "Hello, how are you?", "role": "user"}],
    api_base="http://localhost:11434",
)
print(response)

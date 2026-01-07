from langsmith import Client

client = Client()
prompt = client.pull_prompt("langchain-ai/chat-langchain-response-prompt")

# Add response to docs directory
print(prompt.messages[0].prompt.template)
with open("docs/langchain_response_prompt.txt", "w") as f:
    f.write(prompt.messages[0].prompt.template)

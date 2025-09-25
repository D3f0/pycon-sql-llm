import os
from typing import Dict, List, Annotated, TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from litellm import completion

# Optional: Set your API keys
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
model = os.environ["MODEL"]
# or for other providers:
# os.environ["ANTHROPIC_API_KEY"] = "your-anthropic-api-key"


# Define your state
class AgentState(TypedDict):
    messages: List[HumanMessage | AIMessage | SystemMessage]
    context: Dict


# Create a function that uses LiteLLM to call models
def call_llm(state: AgentState) -> AgentState:
    """Call LLM with LiteLLM."""
    messages = state["messages"]

    # Convert LangChain messages to format expected by LiteLLM
    prompt_messages = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            prompt_messages.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            prompt_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            prompt_messages.append({"role": "assistant", "content": msg.content})

    # Call LiteLLM
    response = completion(
        model="gpt-3.5-turbo",  # You can use any model supported by LiteLLM
        messages=prompt_messages,
        # temperature=0.7,
    )

    # Extract response and add to messages
    assistant_message = AIMessage(content=response.choices[0].message.content)

    return {"messages": messages + [assistant_message], "context": state["context"]}


# Define a function to decide whether to continue or end
def should_continue(state: AgentState) -> str:
    """Determine if we should continue or end."""
    # For example, end after a certain number of messages
    if len(state["messages"]) > 10:
        return END
    return "continue"


# Create the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("llm", call_llm)

# Add edges
workflow.add_edge("llm", should_continue)
workflow.add_conditional_edges("should_continue", should_continue)

# Set the entry point
workflow.set_entry_point("llm")

# Compile the graph
app = workflow.compile()

# Run the graph
result = app.invoke(
    {
        "messages": [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(
                content="Tell me about the relationship between AI and creativity."
            ),
        ],
        "context": {},
    }
)

# Print the final messages
for message in result["messages"]:
    print(f"{message.type}: {message.content}")

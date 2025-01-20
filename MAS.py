from openai import OpenAI
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
from Utility import function_to_schema

client = OpenAI()

class Agent(BaseModel):
    name: str = "Agent"
    model: str = "gpt-4o-mini"
    instructions: str = "You are a helpful Agent"
    tools: list = []
    memory: List[Dict[str, str]] = []  # Memoria locale per ogni agente

        
class Response(BaseModel):
    agent: Optional[Agent]
    messages: list
        
        
def run_full_turn(agent, message):
    current_agent = agent
    current_agent.memory.append({"role": "user", "content": message})  # Aggiungi il messaggio alla memoria locale
    print(f'CURRENT AGENT MEMORY {current_agent} \n\n')
    while True:
        # turn python functions into tools and save a reverse map
        tool_schemas = [function_to_schema(tool) for tool in current_agent.tools]
        tools = {tool.__name__: tool for tool in current_agent.tools}

        # === 1. get openai completion ===
        response = client.chat.completions.create(
            model=current_agent.model,
            messages=[{"role": "system", "content": current_agent.instructions}]
            + current_agent.memory,  # Usa solo la memoria dell'agente corrente
            tools=tool_schemas or None,
        )
        message = response.choices[0].message
        current_agent.memory.append(message)  # Memorizza la risposta

        if message.content:  # print agent response
            print(f"{current_agent.name}:", message.content)

        if not message.tool_calls:  # if finished handling tool calls, break
            break

        # === 2. handle tool calls ===
        for tool_call in message.tool_calls:
            try:
                result = execute_tool_call(tool_call, tools, current_agent.name)
                if type(result) is Agent:  # if agent transfer, update current agent
                    current_agent = result
                    current_agent.memory = [  # Reset memoria per il nuovo agente
                        {"role": "system", "content": current_agent.instructions}
                    ]
                    transfer_message = json.loads(tool_call.function.arguments).get("message", "")
                    if transfer_message:
                        current_agent.memory.append({"role": "user", "content": transfer_message})
                    print(f"Transferred to {current_agent.name} with memory reset: \n{current_agent.memory}")
                    continue  # Restart the loop with the new agent

                result_message = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
                current_agent.memory.append(result_message)  # Memorizza il risultato
            except Exception as e:
                error_message = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Error occurred: {str(e)}",
                }
                current_agent.memory.append(error_message)

    # ==== 3. return last agent used and new messages =====
    return Response(agent=current_agent, messages=current_agent.memory)

def execute_tool_call(tool_call, tools, agent_name):
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)

    print(f"{agent_name}:", f"{name}({args})")

    return tools[name](**args)  # call corresponding function with provided arguments

from pydantic import BaseModel
from typing import Optional


def execute_refund(item_id, reason="not provided"):
    print("\n\n=== Refund Summary ===")
    print(f"Item ID: {item_id}")
    print(f"Reason: {reason}")
    print("=================\n")
    print("Refund execution successful!")
    return "success"

refund_agent = Agent(
    name="Refund Agent",
    instructions="You are a refund agent. Help the user with refunds.",
    tools=[execute_refund],
)

def transfer_to_refunds(message=None):
    """Transfer to the refund agent with an optional message."""
    if message:
        refund_agent.instructions += f"\nAdditional message: {message}"
    print("Transferring to Refund Agent with message:", message)
    return refund_agent

def transfer_to_sales_agent(message=None):
    """Transfer to the sales agent with an optional message."""
    if message:
        sales_agent.instructions += f"\nAdditional message: {message}"
    print("Transferring to Sales Agent with message:", message)
    return sales_agent

def transfer_to_issues_and_repairs(message=None):
    """Transfer to the issues and repairs agent with an optional message."""
    if message:
        issues_and_repairs_agent.instructions += f"\nAdditional message: {message}"
    print("Transferring to Issues and Repairs Agent with message:", message)
    return issues_and_repairs_agent

def transfer_back_to_triage(message=None):
    """Transfer back to the triage agent with an optional message."""
    if message:
        triage_agent.instructions += f"\nAdditional message: {message}"
    print("Transferring back to Triage Agent with message:", message)
    return triage_agent



triage_agent = Agent(
    name="Triage Agent",
    instructions=(
        "You are Triage Agent, a customer service bot for ACME Inc. "
        "Introduce yourself. Always be very brief. "
        "Gather information to direct the customer to the right department. "
        "But make your questions subtle and natural."
        "When transferring to another agent, summarize the issue and any steps already taken to resolve it."
        
    ),
    tools=[transfer_to_sales_agent, transfer_to_issues_and_repairs],
)


def execute_order(product, price: int):
    """Price should be in USD."""
    print("\n\n=== Order Summary ===")
    print(f"Product: {product}")
    print(f"Price: ${price}")
    print("=================\n")
    confirm = input("Confirm order? y/n: ").strip().lower()
    if confirm == "y":
        print("Order execution successful!")
        return "Success"
    else:
        print("Order cancelled!")
        return "User cancelled order."


sales_agent = Agent(
    name="Sales Agent",
    instructions=(
        "You are Sales Agent, a sales agent for ACME Inc."
        "Always answer in a sentence or less."
        "Follow the following routine with the user:"
        "1. Ask them about any problems in their life related to catching roadrunners.\n"
        "2. Casually mention one of ACME's crazy made-up products can help.\n"
        " - Don't mention price.\n"
        "3. Once the user is bought in, drop a ridiculous price.\n"
        "4. Only after everything, and if the user says yes, "
        "tell them a crazy caveat and execute their order.\n"
        "When transferring to another agent, summarize the issue and any steps already taken to resolve it."
    ),
    tools=[execute_order, transfer_back_to_triage],
)


def look_up_item(search_query):
    """Use to find item ID.
    Search query can be a description or keywords."""
    item_id = "item_132612938"
    print("Found item:", item_id)
    return item_id


issues_and_repairs_agent = Agent(
    name="Issues and Repairs Agent",
    instructions=(
        "You are Issues and Repairs Agent, a customer support agent for ACME Inc."
        "Always answer in a sentence or less."
        "Follow the following routine with the user:"
        "1. First, ask probing questions and understand the user's problem deeper.\n"
        " - unless the user has already provided a reason.\n"
        "2. Propose a fix (make one up).\n"
        "3. ONLY if not satesfied, offer a refund.\n"
        "4. If accepted, search for the ID and then execute refund."
        "When transferring to another agent, summarize the issue and any steps already taken to resolve it."
    ),
    tools=[execute_refund, look_up_item, transfer_back_to_triage],
)


# Ciclo di esecuzione
current_agent = triage_agent
while True:
    user_input = input("User: ")
    response = run_full_turn(current_agent, user_input)
    current_agent = response.agent

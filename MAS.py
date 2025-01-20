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

from typing import Optional
import os
import shutil

#################################################################
#                       TOOLS IMPLEMENTATION                    #
#################################################################

def write_code_to_file(file_name: str, code: str):
    """
    Write arbitrary code content to a specified file.
    """
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(code)
    return f"Code written to {file_name}"

def execute_code_from_file(file_name: str):
    """
    Execute Python code from a specified file.
    """
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            code = f.read()
        exec(code, {})
        return "Code executed successfully"
    except Exception as e:
        return f"Execution failed: {e}"

def read_file(file_name: str):
    """
    Read the content of a specified file.
    """
    if not os.path.exists(file_name):
        return f"File {file_name} not found."
    with open(file_name, "r", encoding="utf-8") as f:
        return f.read()

def create_folder(folder_path: str):
    """
    Create a folder at the specified path.
    """
    try:
        os.makedirs(folder_path, exist_ok=True)
        return f"Folder '{folder_path}' created or already exists."
    except Exception as e:
        return f"Error creating folder '{folder_path}': {e}"

def create_project_structure(base_path: str):
    """
    Create the main folders for the project at the specified base path.
    """
    # Structure can be dynamically determined or expanded as needed
    structure = [
        "src",
        "src/core",
        "tests",
        "docs",
    ]
    results = []
    for folder in structure:
        full_path = os.path.join(base_path, folder)
        os.makedirs(full_path, exist_ok=True)
        results.append(f"Created folder: {full_path}")
    return "\n".join(results)

def write_tests(base_path: str):
    """
    Write test files for the project at the specified base path.
    """
    # Placeholder content, to be replaced by actual tests
    test_content = "# Test code content goes here."
    return write_code_to_file(
        os.path.join(base_path, "tests", "test_file.py"),
        test_content
    )

def write_documentation(base_path: str):
    """
    Write documentation files for the project at the specified base path.
    """
    # Placeholder documentation content
    doc_content = "# Documentation content goes here."
    return write_code_to_file(
        os.path.join(base_path, "docs", "README.md"),
        doc_content
    )

def write_project_code(base_path: str):
    """
    Write main project code (e.g. library management system) inside src/.
    """
    # Placeholder code content
    main_code = "# Main project code goes here."
    return write_code_to_file(
        os.path.join(base_path, "src", "core", "main.py"),
        main_code
    )

#################################################################
#                           PLANNER                             #
#################################################################

planner_agent = Agent(
    name="Planner Agent",
    instructions=(
        "I am the Planner Agent. "
        "Il mio compito è fornire il piano generale delle operazioni per l'intero progetto, "
        "tenendo conto degli obiettivi e dei compiti di ciascun agente. "
        "Posso essere consultato da Triage Agent (o da altri agenti) "
        "per avere una visione d'insieme e per capire l'ordine ottimale delle azioni. "
        "Dopo aver fornito le mie informazioni, passo sempre la palla al Triage Agent."
    ),
    tools=[]
)

#################################################################
#                           AGENTS                              #
#################################################################

write_code_agent = Agent(
    name="Write Code Agent",
    instructions=(
        "Io sono il Write Code Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Triage Agent, "
        "Execute Code Agent, File Manager Agent, Project Structure Agent, "
        "Test Writer Agent, Documentation Agent, Project Code Agent, e Project Manager Agent. "
        "Il mio compito è di scrivere codice in un file specificato. "
        "Dopo aver completato il mio compito, restituisco sempre il controllo al Triage Agent."
    ),
    tools=[write_code_to_file],
)

execute_code_agent = Agent(
    name="Execute Code Agent",
    instructions=(
        "Io sono l'Execute Code Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Triage Agent, "
        "Write Code Agent, File Manager Agent, Project Structure Agent, "
        "Test Writer Agent, Documentation Agent, Project Code Agent, e Project Manager Agent. "
        "Il mio compito è di eseguire codice Python da un file. "
        "Dopo l'esecuzione, passo il controllo nuovamente al Triage Agent."
    ),
    tools=[execute_code_from_file],
)

file_manager_agent = Agent(
    name="File Manager Agent",
    instructions=(
        "Io sono il File Manager Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Triage Agent, "
        "Write Code Agent, Execute Code Agent, Project Structure Agent, "
        "Test Writer Agent, Documentation Agent, Project Code Agent, e Project Manager Agent. "
        "Il mio compito è di leggere contenuti da file. "
        "Dopo aver fornito le informazioni lette, restituisco sempre il controllo al Triage Agent."
    ),
    tools=[read_file],
)

project_structure_agent = Agent(
    name="Project Structure Agent",
    instructions=(
        "Io sono il Project Structure Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Triage Agent, "
        "Write Code Agent, Execute Code Agent, File Manager Agent, Test Writer Agent, "
        "Documentation Agent, Project Code Agent, e Project Manager Agent. "
        "Il mio compito è creare le cartelle di base e la struttura del progetto. "
        "Dopo aver completato la creazione, passo il controllo al Triage Agent."
    ),
    tools=[create_folder, create_project_structure],
)

test_writer_agent = Agent(
    name="Test Writer Agent",
    instructions=(
        "Io sono il Test Writer Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Triage Agent, "
        "Write Code Agent, Execute Code Agent, File Manager Agent, Project Structure Agent, "
        "Documentation Agent, Project Code Agent, e Project Manager Agent. "
        "Il mio compito è scrivere test per il progetto. "
        "Dopo aver scritto i test, passo sempre il controllo al Triage Agent."
    ),
    tools=[write_tests],
)

documentation_agent = Agent(
    name="Documentation Agent",
    instructions=(
        "Io sono il Documentation Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Triage Agent, "
        "Write Code Agent, Execute Code Agent, File Manager Agent, Project Structure Agent, "
        "Test Writer Agent, Project Code Agent, e Project Manager Agent. "
        "Il mio compito è scrivere documentazione per il progetto. "
        "Dopo aver completato la scrittura della documentazione, passo il controllo al Triage Agent."
    ),
    tools=[write_documentation],
)

project_code_agent = Agent(
    name="Project Code Agent",
    instructions=(
        "Io sono il Project Code Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Triage Agent, "
        "Write Code Agent, Execute Code Agent, File Manager Agent, Project Structure Agent, "
        "Test Writer Agent, Documentation Agent, e Project Manager Agent. "
        "Il mio compito è scrivere il codice principale del progetto. "
        "Dopo aver completato la scrittura, passo sempre il controllo al Triage Agent."
    ),
    tools=[write_project_code],
)

#################################################################
#                    AGENT TRANSFERS (HANDOFFS)                #
#################################################################
# Questi metodi restituiscono l'agente desiderato,
# ma la conversazione, dopo la chiamata, dovrà comunque tornare al Triage Agent.

def transfer_to_write_code_agent(message=None):
    """Transfer to the Write Code Agent with an optional message."""
    write_code_agent.memory = [{"role": "system", "content": write_code_agent.instructions}]
    if message:
        write_code_agent.memory.append({"role": "user", "content": message})
    print(f"Transferring to Write Code Agent with memory reset: \n{write_code_agent.memory}")
    return write_code_agent

def transfer_to_execute_code_agent(message=None):
    """Transfer to the Execute Code Agent with an optional message."""
    execute_code_agent.memory = [{"role": "system", "content": execute_code_agent.instructions}]
    if message:
        execute_code_agent.memory.append({"role": "user", "content": message})
    print(f"Transferring to Execute Code Agent with memory reset: \n{execute_code_agent.memory}")
    return execute_code_agent

def transfer_to_file_manager_agent(message=None):
    """Transfer to the File Manager Agent with an optional message."""
    file_manager_agent.memory = [{"role": "system", "content": file_manager_agent.instructions}]
    if message:
        file_manager_agent.memory.append({"role": "user", "content": message})
    print(f"Transferring to File Manager Agent with memory reset: \n{file_manager_agent.memory}")
    return file_manager_agent

def transfer_to_project_structure_agent(message=None):
    """Transfer to the Project Structure Agent with an optional message."""
    project_structure_agent.memory = [{"role": "system", "content": project_structure_agent.instructions}]
    if message:
        project_structure_agent.memory.append({"role": "user", "content": message})
    print(f"Transferring to Project Structure Agent with memory reset: \n{project_structure_agent.memory}")
    return project_structure_agent

def transfer_to_test_writer_agent(message=None):
    """Transfer to the Test Writer Agent with an optional message."""
    test_writer_agent.memory = [{"role": "system", "content": test_writer_agent.instructions}]
    if message:
        test_writer_agent.memory.append({"role": "user", "content": message})
    print(f"Transferring to Test Writer Agent with memory reset: \n{test_writer_agent.memory}")
    return test_writer_agent

def transfer_to_documentation_agent(message=None):
    """Transfer to the Documentation Agent with an optional message."""
    documentation_agent.memory = [{"role": "system", "content": documentation_agent.instructions}]
    if message:
        documentation_agent.memory.append({"role": "user", "content": message})
    print(f"Transferring to Documentation Agent with memory reset: \n{documentation_agent.memory}")
    return documentation_agent

def transfer_to_project_code_agent(message=None):
    """Transfer to the Project Code Agent with an optional message."""
    project_code_agent.memory = [{"role": "system", "content": project_code_agent.instructions}]
    if message:
        project_code_agent.memory.append({"role": "user", "content": message})
    print(f"Transferring to Project Code Agent with memory reset: \n{project_code_agent.memory}")
    return project_code_agent

def transfer_to_planner_agent(message=None):
    """Transfer to the Planner Agent with an optional message."""
    planner_agent.memory = [{"role": "system", "content": planner_agent.instructions}]
    if message:
        planner_agent.memory.append({"role": "user", "content": message})
    print(f"Transferring to Planner Agent with memory reset: \n{planner_agent.memory}")
    return planner_agent


#################################################################
#                          TRIAGE AGENT                         #
#################################################################

triage_agent = Agent(
    name="Triage Agent",
    instructions=(
        "Io sono il Triage Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Write Code Agent, "
        "Execute Code Agent, File Manager Agent, Project Structure Agent, Test Writer Agent, "
        "Documentation Agent, Project Code Agent, e Project Manager Agent. "
        "Il mio compito è valutare le richieste in arrivo e inoltrarle all'agente più appropriato. "
        "Inoltre, consulto il Planner Agent per avere una visione d'insieme "
        "e prendere decisioni con più contesto. "
        "Dopo che un agente risponde, riporto sempre la conversazione a me stesso per ulteriori decisioni. "
        "Ordine tipico per setup di progetto: \n"
        "1. Project Structure Agent (creazione struttura)\n"
        "2. File Manager Agent (lettura file se necessario)\n"
        "3. Project Code Agent (scrittura codice principale)\n"
        "4. Test Writer Agent (scrittura test)\n"
        "5. Documentation Agent (creazione documentazione)\n"
        "6. Execute Code Agent (esecuzione del codice, se richiesto)\n\n"
        "Strumenti di routing disponibili (funzioni transfer_to_*): "
        "Write Code, Execute Code, File Manager, Project Structure, Test Writer, Documentation, "
        "Project Code e Planner. "
        "Alla fine di ogni chiamata a un agente, il flusso torna a me."
    ),
    tools=[
        transfer_to_planner_agent,
        transfer_to_write_code_agent,
        transfer_to_execute_code_agent,
        transfer_to_file_manager_agent,
        transfer_to_project_structure_agent,
        transfer_to_test_writer_agent,
        transfer_to_documentation_agent,
        transfer_to_project_code_agent,
    ],
)

#################################################################
#                     PROJECT MANAGEMENT AGENT                  #
#################################################################

project_manager_agent = Agent(
    name="Project Manager Agent",
    instructions=(
        "Io sono il Project Manager Agent. "
        "Opero in un ambiente multi-agente che include: Planner Agent, Triage Agent, "
        "Write Code Agent, Execute Code Agent, File Manager Agent, "
        "Project Structure Agent, Test Writer Agent, Documentation Agent e Project Code Agent. "
        "Il mio compito è gestire l'intero ciclo di vita del progetto, "
        "coordinando la creazione della struttura, la scrittura del codice, "
        "i test e la documentazione. "
        "Nel fare ciò, posso anche consultare il Planner Agent. "
        "Una volta terminato un compito, riconsegno il controllo al Triage Agent."
    ),
    tools=[
        create_project_structure,
        write_project_code,
        write_tests,
        write_documentation,
        execute_code_from_file,
    ],
)

#################################################################
#                    OPTIONAL INTERACTION LOOP                  #
#################################################################

def run_interaction_loop():
    """
    Optional loop for user input, if needed.
    """
    # Ciclo di esecuzione
    current_agent = triage_agent
    while True:
        user_input = input("User: ")
        response = run_full_turn(current_agent, user_input)
        current_agent = response.agent

if __name__ == "__main__":
    run_interaction_loop()

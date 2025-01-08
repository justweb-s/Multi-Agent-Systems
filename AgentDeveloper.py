from openai import OpenAI

# Configura il client OpenAI
client = OpenAI(api_key="La-TUA-API")

# Agenti specializzati
class ArchitectAgent:
    def process(self, project_description):
        messages = [
            {
                "role": "system",
                "content": (
                    "Sei un architetto software. Progetta l'architettura per il seguente progetto. "
                    "Rispondi in un formato strutturato come segue:\n\n"
                    "### Descrizione Generale\n"
                    "- Breve overview del sistema.\n\n"
                    "### Moduli Principali\n"
                    "- Nome Modulo: [Breve descrizione del modulo e delle sue responsabilità.]\n"
                    "- Nome Modulo: [Breve descrizione del modulo e delle sue responsabilità.]\n\n"
                    "### Struttura della Cartella del Progetto\n"
                    "```\n"
                    "root/\n"
                    "    module1/\n"
                    "        file1.py\n"
                    "        file2.py\n"
                    "    module2/\n"
                    "        file3.py\n"
                    "    tests/\n"
                    "        test_module1.py\n"
                    "        test_module2.py\n"
                    "    README.md\n"
                    "    requirements.txt\n"
                    "```\n"
                )
            },
            {"role": "user", "content": project_description}
        ]
        response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
        return response.choices[0].message.content



class DeveloperAgent:
    def process(self, module_description):
        messages = [
            {"role": "system", "content": "Sei uno sviluppatore. Scrivi il codice per il seguente modulo."},
            {"role": "user", "content": module_description}
        ]
        response = client.chat.completions.create(model="gpt-4o", messages=messages)
        return response.choices[0].message.content


class DebuggerAgent:
    def process(self, code_snippet):
        messages = [
            {"role": "system", "content": "Sei un debug esperto. Trova e correggi i bug in questo codice."},
            {"role": "user", "content": code_snippet}
        ]
        response = client.chat.completions.create(model="gpt-4o", messages=messages)
        return response.choices[0].message.content


class DocumenterAgent:
    def process(self, code_snippet):
        messages = [
            {"role": "system", "content": "Sei un esperto documentatore. Scrivi la documentazione tecnica per questo codice."},
            {"role": "user", "content": code_snippet}
        ]
        response = client.chat.completions.create(model="gpt-4o", messages=messages)
        return response.choices[0].message.content


class SupervisorAgent:
    def __init__(self):
        self.agents = {
            "architect": ArchitectAgent(),
            "developer": DeveloperAgent(),
            "debugger": DebuggerAgent(),
            "documenter": DocumenterAgent()
        }
        self.project_context = {
            "description": "",
            "architecture": "",
            "folders": {},  # Struttura: {"folder_path": ["file1.py", "file2.py"]}
            "files": {}  # Struttura: {"file_path": "file_content"}
        }

    def parse_folder_structure(self, folder_structure):
        """Converte una struttura di cartelle in un dizionario."""
        lines = folder_structure.strip().split("\n")
        current_path = []
        folders = {}

        for line in lines:
            indent_level = len(line) - len(line.lstrip())
            name = line.strip()

            # Determina se è una cartella o un file
            if name.endswith("/"):
                current_path = current_path[:indent_level // 4]  # Rimuovi livelli extra
                current_path.append(name[:-1])
                folder_key = "/".join(current_path)
                folders[folder_key] = []
            else:
                folder_key = "/".join(current_path)
                folders[folder_key].append(name)

        return folders

    def route_task(self, task_type, content):
        agent = self.agents.get(task_type)
        if not agent:
            raise ValueError(f"Agente non trovato per il tipo {task_type}")
        
        # Includi il contesto del progetto nei messaggi per gli agenti
        full_context = f"Progetto: {self.project_context['description']}\n"
        full_context += f"Architettura: {self.project_context['architecture']}\n"
        full_context += "Struttura delle cartelle:\n"
        for folder, files in self.project_context["folders"].items():
            full_context += f"{folder}/\n"
            for file in files:
                full_context += f"    {file}\n"

        messages = [
            {"role": "system", "content": full_context},
            {"role": "user", "content": content}
        ]
        response = agent.process(content)
        return response

    def manage_project(self, project_description):
        self.project_context["description"] = project_description

        # Step 1: Progettazione
        architecture = self.route_task("architect", project_description)
        self.project_context["architecture"] = architecture
        print(f'Aechitetture: ', architecture)
        # Estrarre la struttura delle cartelle
        sections = architecture.split("###")
        folder_section = next((s for s in sections if "Struttura della Cartella del Progetto" in s), None)

        if folder_section:
            folder_structure = folder_section.split("```")[1]  # Prendi il blocco di codice
            self.project_context["folders"] = self.parse_folder_structure(folder_structure)
        else:
            print("Struttura delle cartelle non trovata nell'architettura.")
            return

        # Step 2: Sviluppo
        for folder, files in self.project_context["folders"].items():
            for file in files:
                file_path = f"{folder}/{file}"
                file_description = f"Genera il contenuto per il file '{file}' situato in '{folder}/'."
                file_content = self.route_task("developer", file_description)
                self.project_context["files"][file_path] = file_content
                print(f"Generato file '{file_path}':\n", file_content)
                input()  # Pausa per l'utente tra i file


        # Step 3: Debug
        debugged_code = []
        for snippet in code:
            corrected_code = self.route_task("debugger", snippet)
            print("Codice debug:", corrected_code)
            debugged_code.append(corrected_code)

        # Step 4: Documentazione
        documentation = []
        for snippet in debugged_code:
            doc = self.route_task("documenter", snippet)
            print("Documentazione:", doc)
            documentation.append(doc)

        return {
            "architecture": architecture,
            "code": debugged_code,
            "documentation": documentation
        }

# Esecuzione del sistema##
if __name__ == "__main__":
    supervisor = SupervisorAgent()
    
    # Input utente
    project = "Crea un sistema per gestire le prenotazioni di un ristorante, con funzionalità per creare, aggiornare e cancellare prenotazioni."
    project_result = supervisor.manage_project(project)
    
    print("\nProgetto completato:", project_result)

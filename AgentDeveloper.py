import os
import re
import subprocess
from openai import OpenAI

# Inizializzazione del client OpenAI
client = OpenAI(api_key="API")

def extract_code(content: str) -> str:
    """
    Estrae il primo blocco di codice presente tra i delimitatori ```...```.
    Se non è presente alcun blocco, restituisce il contenuto così com'è.
    """
    pattern = r"```(?:[\w+]*)\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)
    return matches[0] if matches else content


class ArchitectAgent:
    """
    L'Architetto si occupa di:
      1. Definire l'architettura del progetto in modo dettagliato.
      2. Fornire UML di alto livello per i principali componenti, classi e relazioni.
      3. Struttura della cartella del progetto.
    """
    def process(self, combined_context: str) -> str:
        """
        combined_context è una stringa che include:
          - Descrizione del progetto
          - Contesto attuale (self.project_context)
          - Istruzioni per l'architetto
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "Sei un architetto software. Il tuo compito è:"
                    "\n1. Fornire una descrizione chiara e completa del progetto, includendo UML (diagramma di classi)."
                    "\n2. Definire i moduli principali e le responsabilità di ciascuno."
                    "\n3. Specificare la struttura della cartella del progetto in un blocco di codice."
                    "\n\nRispondi con un formato strutturato, ad esempio:"
                    "\n### Descrizione Generale"
                    "\n- [Descrizione del sistema]"
                    "\n\n### UML"
                    "\n```\n[Diagramma UML testuale, es. PlantUML o descrizione testuale]\n```"
                    "\n\n### Moduli Principali"
                    "\n- [Nome Modulo]: [Breve descrizione]"
                    "\n\n### Struttura della Cartella del Progetto"
                    "\n```\nroot/\n    module1/\n        file1.py\n    ...\n```"
                )
            },
            {
                "role": "user",
                "content": combined_context
            }
        ]
        response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
        return response.choices[0].message.content


class DeveloperAgent:
    """
    Lo Sviluppatore riceve:
      - il contesto completo del progetto (descrizione, architettura, UML, ecc.)
      - le istruzioni specifiche per un determinato file o modulo
    Restituisce il contenuto del file (codice) racchiuso in un blocco ```...```.
    """
    def process(self, task_description: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Sei uno sviluppatore. Hai accesso alle informazioni di progetto (architettura, UML, etc.)."
                    "Scrivi il codice per il file richiesto, includendolo in un blocco di codice ```...```."
                )
            },
            {"role": "user", "content": task_description}
        ]
        response = client.chat.completions.create(model="gpt-4o", messages=messages)
        return response.choices[0].message.content


class DebuggerAgent:
    """
    Il Debugger riceve:
      - tutto il contesto di progetto (architettura, UML, file generato, errore)
      - fornisce un codice corretto, racchiuso in un blocco ```...```.
    """
    def process(self, debug_info: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Sei un esperto debug. Hai a disposizione il progetto completo (architettura, UML, codice) e l'errore."
                    "Correggi il codice e racchiudi la versione corretta in un blocco ```...```."
                )
            },
            {"role": "user", "content": debug_info}
        ]
        response = client.chat.completions.create(model="gpt-4o", messages=messages)
        return response.choices[0].message.content


class DocumenterAgent:
    """
    Il Documentatore riceve il codice del progetto (o snippet) per scrivere la documentazione.
    """
    def process(self, code_snippet: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Sei un esperto documentatore. Scrivi la documentazione tecnica per il seguente codice."
                )
            },
            {"role": "user", "content": code_snippet}
        ]
        response = client.chat.completions.create(model="gpt-4o", messages=messages)
        return response.choices[0].message.content


class SupervisorAgent:
    """
    Il Supervisore:
      - Mantiene e aggiorna il contesto generale del progetto.
      - Esegue i task nell'ordine stabilito (Architettura -> Sviluppo -> Debug -> ecc.).
      - Fornisce ad ogni agente il contesto necessario.
    """
    def __init__(self):
        self.agents = {
            "architect": ArchitectAgent(),
            "developer": DeveloperAgent(),
            "debugger": DebuggerAgent(),
            "documenter": DocumenterAgent()
        }
        # Questo dizionario contiene tutte le info di contesto che vengono arricchite passo passo
        self.project_context = {
            "description": "",
            "architecture": "",
            "uml": "",
            "folders": {},   # {"folder_path": ["file1.py", "file2.py"]}
            "files": {},     # {"file_path": "contenuto_file"}
        }

    def parse_folder_structure(self, folder_structure: str) -> dict:
        """
        Converte la struttura testuale delle cartelle in un dizionario.
        """
        lines = folder_structure.strip().split("\n")
        current_path = []
        folders = {}

        for line in lines:
            indent_level = len(line) - len(line.lstrip())
            name = line.strip()

            if not name:
                continue

            if name.endswith("/"):
                current_path = current_path[:indent_level // 4]
                current_path.append(name[:-1])
                folder_key = "/".join(current_path)
                folders[folder_key] = []
            else:
                folder_key = "/".join(current_path)
                if folder_key not in folders:
                    folders[folder_key] = []
                folders[folder_key].append(name)

        return folders

    def create_project_structure(self, root_folder: str = "root") -> None:
        """
        Crea fisicamente la struttura delle cartelle e file vuoti sul filesystem,
        in base a self.project_context["folders"].
        """
        for folder, files in self.project_context["folders"].items():
            dir_path = os.path.join(root_folder, folder)
            os.makedirs(dir_path, exist_ok=True)
            for file in files:
                file_path = os.path.join(dir_path, file)
                if not os.path.exists(file_path):
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("")

    def route_task(self, agent_type: str, content: str) -> str:
        """
        Route di comodo per interfacciarsi con i vari agenti.
        """
        agent = self.agents.get(agent_type)
        if not agent:
            raise ValueError(f"Agente '{agent_type}' non trovato.")
        return agent.process(content)

    def manage_project(self, project_description: str):
        #
        # Salviamo la descrizione del progetto nel contesto
        #
        self.project_context["description"] = project_description

        #
        # Step 1: ARCHITETTURA (incluso UML)
        #
        # Unifichiamo la descrizione del progetto e il contesto in un'unica stringa
        arch_input_context = (
            f"Descrizione progetto: {project_description}\n\n"
            f"Contesto attuale (dizionario Python): {self.project_context}\n\n"
            "Fornisci un'architettura dettagliata e un UML di alto livello."
        )
        architecture_full = self.route_task("architect", arch_input_context)
        self.project_context["architecture"] = architecture_full

        # Cerchiamo le sezioni UML e Struttura Cartelle
        sections = architecture_full.split("###")

        # UML
        uml_section = next((s for s in sections if "UML" in s), None)
        if uml_section and "```" in uml_section:
            uml_code = uml_section.split("```")[1]
            self.project_context["uml"] = uml_code.strip()
        else:
            self.project_context["uml"] = "Nessun UML fornito."

        # Folder structure
        folder_section = next((s for s in sections if "Struttura della Cartella del Progetto" in s), None)
        if folder_section and "```" in folder_section:
            folder_structure = folder_section.split("```")[1]
            self.project_context["folders"] = self.parse_folder_structure(folder_structure)
        else:
            print("Struttura cartelle non trovata o mal formattata nell'architettura.")
            return

        # Creiamo la struttura fisica
        self.create_project_structure()

        print("\n--- ARCHITETTURA COMPLETA ---")
        print(architecture_full)
        print("\n--- UML ---")
        print(self.project_context["uml"])
        print("\n--- STRUTTURA CARTELLE ---")
        for k, v in self.project_context["folders"].items():
            print(f"{k} -> {v}")

        #
        # Step 2: SVILUPPO
        #
        for folder, files in self.project_context["folders"].items():
            for file_name in files:
                file_path = os.path.join("root", folder, file_name)

                # Creiamo una descrizione per lo sviluppatore
                dev_input_context = (
                    f"Contesto del progetto:\n"
                    f"- Descrizione: {self.project_context['description']}\n"
                    f"- Architettura: {self.project_context['architecture']}\n"
                    f"- UML: {self.project_context['uml']}\n\n"
                    f"Devi generare il contenuto per il file {file_name} nella cartella {folder}/.\n"
                    f"Fornisci solo il codice, racchiuso tra triple backticks."
                )
                developer_response = self.route_task("developer", dev_input_context)
                file_content = extract_code(developer_response)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(file_content)

                print(f"\n--- FILE GENERATO: {file_path} ---")
                print(file_content)

                # Se è un file Python, lo eseguiamo e intercettiamo eventuali errori
                if file_name.endswith(".py"):
                    try:
                        process = subprocess.run(["python", file_path], capture_output=True, text=True)
                        stdout = process.stdout
                        stderr = process.stderr

                        if stdout:
                            print(f"\n[OUTPUT ESECUZIONE] {file_path}:\n{stdout}")
                        if stderr:
                            print(f"\n[ERRORI ESECUZIONE] {file_path}:\n{stderr}")

                            # Richiesta di debug: forniamo all'agente contesto completo + codice + errore
                            with open(file_path, "r", encoding="utf-8") as code_file:
                                current_code = code_file.read()

                            debug_context = (
                                f"Contesto del progetto:\n"
                                f"- Descrizione: {self.project_context['description']}\n"
                                f"- Architettura: {self.project_context['architecture']}\n"
                                f"- UML: {self.project_context['uml']}\n\n"
                                f"Errore incontrato nell'esecuzione di {file_path}:\n{stderr}\n\n"
                                f"Codice attuale:\n{current_code}"
                            )
                            debug_response = self.route_task("debugger", debug_context)
                            corrected_code = extract_code(debug_response)

                            # Sovrascrive il file con il codice corretto
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(corrected_code)

                            print(f"\n--- CODICE CORRETTO ({file_path}) ---\n{corrected_code}")

                            # Eventuale riesecuzione dopo correzione
                            try:
                                retry_process = subprocess.run(["python", file_path], capture_output=True, text=True)
                                if retry_process.stdout:
                                    print(f"\n[OUTPUT RIESECUZIONE] {file_path}:\n{retry_process.stdout}")
                                if retry_process.stderr:
                                    print(f"\n[ERRORI DOPO CORREZIONE] {file_path}:\n{retry_process.stderr}")
                            except Exception as re_ex:
                                print(f"Errore nella riesecuzione di {file_path} dopo la correzione: {re_ex}")

                    except Exception as ex:
                        print(f"Errore durante l'esecuzione di {file_path}: {ex}")

                input("\nPremi Invio per continuare...")

        #
        # Step 3: ALTRE FASI (Documentazione, ecc.) - se necessario
        #

        return {
            "architecture": self.project_context["architecture"],
            "uml": self.project_context["uml"],
            "folders": self.project_context["folders"]
        }


if __name__ == "__main__":
    supervisor = SupervisorAgent()
    # Esempio di progetto
    project = "Crea un semplice sistema per la gestione delle prenotazioni di un ristorante."
    result = supervisor.manage_project(project)

    print("\n--- PROGETTO COMPLETATO ---")
    print("UML:", result["uml"])
    print("Struttura Cartelle:", result["folders"])
    print("--------------------------")

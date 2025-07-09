# agent_module.py

from typing import TypedDict, Optional, List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain.chat_models import init_chat_model

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent,Tool
from pydantic import BaseModel


from dotenv import load_dotenv
import subprocess, requests, os, difflib
import tools

load_dotenv()

api_key = os.getenv('openai_api_key')
WORKSPACE_ROOT=os.getenv('WORKSPACE_ROOT')

# -----------------------------
# TypedDict for Graph State
# -----------------------------
class AgentState(TypedDict):
    input: str
    repo_path: str
    plan: Optional[str]
    code_diff: Optional[str]
    test_result: Optional[Dict[str, Any]]
    FAIL_TO_PASS: List[str]
    PASS_TO_PASS: List[str]
    instance_id: str

# -----------------------------
# Setup local LLM ()
# -----------------------------
# llm = ChatOpenAI(
#    openai_api_base="http://188.245.32.59:4000/v1",
#    model = "gpt-4o-mini",
#    temperature=0.0,
#    max_tokens=8096,
#    api_key=api_key
# )
llm = init_chat_model("google_genai:gemini-2.0-flash")
# -----------------------------
# PLANNER NODE
# -----------------------------
PLANNER_PROMPT = PromptTemplate.from_template("""
You are a software engineer. Given the following bug report and failing test case description, write a clear and minimal step-by-step plan to fix the issue in the code.

Bug Description:
{input}

Write your step-by-step plan below:
""")

planner_chain = PLANNER_PROMPT | llm | StrOutputParser()

def planner_node(state: AgentState) -> Dict[str, Any]:
    print("Planner is generating a plan...")
    plan = planner_chain.invoke({"input": state["input"]})
    print("Planner output:\n", plan)
    return {"plan": plan}



@tool
def list_python_files(repo_path: str) -> list:
    """Recursively list allfiles in a directory."""
    if not repo_path:
        raise ValueError("repo_path is emtpy")

     # Falls repo_path nur ein Verzeichnisname ist, ergänze WORKSPACE_ROOT
    if not os.path.isabs(repo_path):
        repo_path = os.path.join(WORKSPACE_ROOT, repo_path)

    repo_path = r"D:\ProgrammingProjekts\ASE\repos\repo_13"
    py_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):  # optional Filter für Python-Dateien
                py_files.append(os.path.join(root, file))
    return py_files

@tool
def read_file(file_path: str) -> str:
    """Reads a file and returns its contents."""
    file_path = file_path.strip().strip('"').strip("'")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

class ApplyPatchInput(BaseModel):
    file_path: str
    diff: str

#@tool(args_schema=ApplyPatchInput)
def apply_patch(file_path: str, diff: str) -> str:
    """
    Apply a unified-diff patch to the file at file_path.
    Only the hunks present in `diff` are applied.
    """
    print("Apply Patch:  " + file_path)
    file_path = file_path.strip('"').strip("'")
    print("Apply Patch:  " + file_path)

    original = open(file_path, 'r', encoding='utf-8').read().splitlines(keepends=True)
    patched = ''.join(difflib.restore(diff.splitlines(keepends=True), 1))
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(patched)
    return f"Patch applied to {file_path}"

toolSetO=[tools.replace_string,tools.list_files_in_repository,tools.list_dir,tools.read_file,tools.delete_lines,tools.insert_at_line,tools.replace_lines_tool,tools.overwrite_file,tools.find_and_replace]

# -----------------------------
# CODER NODE
# -----------------------------

# --- CODER AGENT ---
coder_prompt = ChatPromptTemplate.from_messages([
    ("system","""You are a code repair agent. The repo path is: {repo_path}.
        When calling tools with paths then include the repo in it. 
        Use Absolute Paths to call tools.
        Do NOT modify file inside the ./git dir.
        Do NOT call list_files_in_repository with {{}}.
        Use tools to make changes. ALWAYS call tools with named parameters in JSON format.
        
        Inspect the code to fix the bug. Do not run tests."""),
    ("human", "The plan for fixing the bug is:\n\n{input}"),
    MessagesPlaceholder("agent_scratchpad")
])

prompt = coder_prompt  # your structured prompt from above
agent = create_tool_calling_agent(llm, toolSetO, prompt)
agent_executor = AgentExecutor(agent=agent, tools=toolSetO, verbose=True)


#agent_executor = initialize_agent( tools, llm, agent="zero-shot-react-description", verbose=True)
# --- CODER NODE ---
def coder_node(state: AgentState) -> Dict[str, Any]:
    print("Coder agent is repairing the code...")
    result = agent_executor.invoke({
        "input": state["plan"],
        "repo_path": state["repo_path"]
    })


    diff = subprocess.run(["git", "diff"], cwd=state["repo_path"], capture_output=True, text=True)
    return {"code_diff": diff.stdout}
# -----------------------------
# TESTER NODE
# -----------------------------
def run_tests(repo_path: str, fail_tests: list, pass_tests: list, instance_id: str) -> dict:
    payload = {
        "instance_id": instance_id,
        "repoDir": repo_path.replace("\\", "/").replace("D:/ProgrammingProjekts/ASE", ""),  # adjust for Docker mount
        "FAIL_TO_PASS": fail_tests,
        "PASS_TO_PASS": pass_tests
    }
    res = requests.post("http://localhost:8082/test", json=payload)
    res.raise_for_status()
    return res.json()

def tester_node(state: AgentState) -> Dict[str, Any]:
    print("Tester is running test suite...")
    result = run_tests(
        repo_path=state["repo_path"],
        fail_tests=state["FAIL_TO_PASS"],
        pass_tests=state["PASS_TO_PASS"],
        instance_id=state["instance_id"]
    )
    print("Test results:", result)
    return {"test_result": result}

# -----------------------------
# LANGGRAPH COMPOSITION
# -----------------------------
builder = StateGraph(AgentState)

builder.add_node("planner", planner_node)
builder.add_node("coder", coder_node)


builder.set_entry_point("planner")
builder.add_edge("planner", "coder")

builder.add_edge("coder", END)


coding_agent = builder.compile()

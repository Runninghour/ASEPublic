import asyncio
import json
import os
import requests
import subprocess
from dotenv import load_dotenv

# Prevent PraisonAI from crashing if OpenAI variables are missing
os.environ.setdefault("OPENAI_API_KEY", "not-needed")
os.environ.setdefault("OPENAI_API_BASE", "http://localhost:1234/v1")

from prompts import planner_prompt, coder_prompt, tester_prompt
from praisonaiagents import Agent, Agents, Tools
from praisonaiagents.tools import execute_code, analyze_code, format_code, lint_code, disassemble_code


load_dotenv()

# Use Gemini via AI Studio with API key
os.environ.setdefault("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
# Prevent LiteLLM from defaulting to Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"


API_KEY = os.getenv("GOOGLE_API_KEY")

API_URL = "http://localhost:8081/task/index/"
TEST_URL = "http://localhost:8082/test"
REPOS_DIR = "repos"
LOG_FILE = "results.log"
WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT")
os.environ.get("WORKSPACE_ROOT")
os.environ["GOOGLE_API_KEY"] = API_KEY




llm_config = {
    "model": "gemini/gemini-2.0-flash",
    "temperature": 0,
    "max_tokens": 4096,
    "api_key": os.getenv("GEMINI_API_KEY"),
    "api_base": "https://generativelanguage.googleapis.com/v1beta",
    "llm_provider": "gemini",  # ensure LiteLLM picks the right route
}




async def handle_task(index):

    print(f"Fetching test case {index} from {API_URL}...")
    repo_dir = os.path.join(WORKSPACE_ROOT, f"repo_{index}")  # Use unique repo directory per task
    start_dir = os.getcwd()  # Remember original working directory
    os.environ["REPO_NAME"] = f"repo_{index}"
    load_dotenv()

    try:
        response = requests.get(f"{API_URL}{index}")
        if response.status_code != 200:
            raise Exception(f"Invalid response: {response.status_code}")

        testcase = response.json()
        prompt = testcase["Problem_statement"]
        git_clone = testcase["git_clone"]
        fail_tests = json.loads(testcase.get("FAIL_TO_PASS", "[]"))
        pass_tests = json.loads(testcase.get("PASS_TO_PASS", "[]"))
        instance_id = testcase["instance_id"]

        # Extract repo URL and commit hash
        parts = git_clone.split("&&")
        clone_part = parts[0].strip()
        checkout_part = parts[-1].strip() if len(parts) > 1 else None

        repo_url = clone_part.split()[2]

        print(f"Cloning repository {repo_url} into {repo_dir}...")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        if not os.path.isdir(os.environ.get('WORKSPACE_ROOT', '') +'\\'+ os.environ.get('REPO_NAME', '')):
            subprocess.run(["git", "clone", repo_url, repo_dir], check=True, env=env)

        if checkout_part:
           commit_hash = checkout_part.split()[-1]
           print(f"Checking out commit: {commit_hash}")
           subprocess.run(["git", "checkout", commit_hash], cwd=repo_dir, check=True, env=env)


        tools = [execute_code, analyze_code, format_code, lint_code, disassemble_code]

        planner = Agent(
            instructions=planner_prompt,
            llm=llm_config
        )

        coder = Agent(
            instructions=coder_prompt,
            llm=llm_config,
            tools=tools
        )

        tester = Agent(
            instructions=tester_prompt,
            llm=llm_config,
            tools=tools
        )

        agents = Agents(agents=[planner, coder, tester])

        full_prompt = (
            f"Work in the directory: {os.environ.get("WORKSPACE_ROOT")}\\repo_{index}. This is a Git repository.\n"
            f"Your goal is to fix the problem described below.\n"
            f"All code changes must be saved to the files, so they appear in `git diff`.\n"
            f"Problem description:\n"
            f"{prompt}\n\n"
            f"Make sure the fix is minimal and only touches what's necessary to resolve the failing tests."
        )

        agents.start(task_content=full_prompt)

        test_payload = {
            "instance_id": instance_id,
            "repoDir": f"/repos/repo_{index}",
            "FAIL_TO_PASS": fail_tests,
            "PASS_TO_PASS": pass_tests
        }

        res = requests.post(TEST_URL, json=test_payload)
        res.raise_for_status()
        result_raw = res.json().get("harnessOutput", "{}")
        result_json = json.loads(result_raw)
        if not result_json:
            raise ValueError("No data in harnessOutput – possible evaluation error or empty result")
        instance_id = next(iter(result_json))
        tests_status = result_json[instance_id]["tests_status"]
        fail_pass_results = tests_status["FAIL_TO_PASS"]
        fail_pass_total = len(fail_pass_results["success"]) + len(fail_pass_results["failure"])
        fail_pass_passed = len(fail_pass_results["success"])
        pass_pass_results = tests_status["PASS_TO_PASS"]
        pass_pass_total = len(pass_pass_results["success"]) + len(pass_pass_results["failure"])
        pass_pass_passed = len(pass_pass_results["success"])

        # Log results
        os.chdir(start_dir)
        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"\n--- TESTCASE {index} ---\n")
            log.write(f"FAIL_TO_PASS passed: {fail_pass_passed}/{fail_pass_total}\n")
            log.write(f"PASS_TO_PASS passed: {pass_pass_passed}/{pass_pass_total}\n")
        print(f"Test case {index} completed and logged.")

    except Exception as e:
        os.chdir(start_dir)
        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"\n--- TESTCASE {index} ---\n")
            log.write(f"Error: {e}\n")
        print(f"Error in test case {index}: {e}")


async def main():
    #for i in range(1, 10):
        await handle_task(13)


if __name__ == "__main__":
    asyncio.run(main())
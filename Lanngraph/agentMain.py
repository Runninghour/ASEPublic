import asyncio
import json
import re

import requests
import subprocess
import os

from your_langgraph_agent_moduleOpenAi import coding_agent

API_URL = "http://localhost:8081/task/index/"  # API endpoint for SWE-Bench-Lite
LOG_FILE = "results.log"
WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT")


async def handle_task(index):
    api_url = f"{API_URL}{index}"
    print(f"Fetching test case {index} from {api_url}...")
    repo_dir = os.path.join(WORKSPACE_ROOT, f"repo_{index}")  # Use unique repo directory per task
    start_dir = os.getcwd()  # Remember original working directory
    os.environ["REPO_NAME"] = f"repo_{index}"

    try:
        response = requests.get(api_url)
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

        # Build full prompt for the agent
        full_prompt = (
            f"You are a team of agents with the following roles:\n"
            f"- Planner: breaks down the problem into coding tasks\n"
            f"- Coder: makes actual changes to the code files in the Git repository\n"
            f"Work in the directory: repo_{index}. This is a Git repository.\n"
            f"Your goal is to fix the problem described below.\n"
            f"All code changes must be saved to the files, so they appear in `git diff`.\n"
            f"The fix will be verified by running the affected tests. Do not run tests yourself\n\n"
            f"Problem description:\n"
            f"{prompt}\n\n"
            f"Make sure the fix is minimal and only touches what's necessary to resolve the failing tests."
        )

        # Launch Agent here
        print(f"Launching agent...")



        agent_input = {
            "input": full_prompt,
            "repo_path": repo_dir,
            "FAIL_TO_PASS": fail_tests,
            "PASS_TO_PASS": pass_tests,
            "instance_id": instance_id,
        }

        response = await coding_agent.ainvoke(agent_input)
        print("Agent finished:", response)

        # Token usage
        #token_total = extract_last_token_total_from_logs() Todo

        # Call REST service instead for evaluation changes from agent
        print(f"Calling SWE-Bench REST service with repo: {repo_dir}")
        test_payload = {
            "instance_id": instance_id,
            "repoDir": f"/repos/repo_{index}",  # mount with docker
            "FAIL_TO_PASS": fail_tests,
            "PASS_TO_PASS": pass_tests
        }
        res = requests.post("http://localhost:8082/test", json=test_payload)
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
            log.write(f"Total Tokens Used: {"not "}\n") # Todo
        print(f"Test case {index} completed and logged.")

    except Exception as e:
     os.chdir(start_dir)
     with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"\n--- TESTCASE {index} ---\n")
        log.write(f"Error: {e}\n")
     print(f"Error in test case {index}: {e}")


def extract_last_token_total_from_logs():
    log_dir = r"logs"
    log_files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
    if not log_files:
        return "No logs found"

    log_files.sort(reverse=True)

    latest_log_path = os.path.join(log_dir, log_files[0])
    with open(latest_log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in reversed(lines):
        match = re.search(r'Cumulative Total=(\d+)', line)
        if match:
            return int(match.group(1))

    return "Cumulative Total not found"


async def main():
     #for i in range(1, 31):
        await handle_task(1)


if __name__ == "__main__":
    asyncio.run(main())

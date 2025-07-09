import sys
import warnings

from datetime import datetime

from dotenv import load_dotenv

from crew import ASE
import asyncio
import json

import requests
import subprocess
import os
import stat
import shutil

from langchain_community.agent_toolkits import FileManagementToolkit
from crewai_tools import (
    FileReadTool, DirectoryReadTool,FileWriterTool

)


API_KEY = os.getenv("GOOGLE_API_KEY")
load_dotenv()
API_URL = "http://localhost:8081/task/index/"
TEST_URL = "http://localhost:8082/test"
REPOS_DIR = "repos"
LOG_FILE = "results.log"
WORKSPACE_ROOT= "D:\\ProgrammingProjekts\\ASEPublic\\repos"
os.environ.get("WORKSPACE_ROOT")
os.environ["GOOGLE_API_KEY"] = API_KEY





async def handle_task(index):
    load_dotenv()
    api_url = f"{API_URL}{index}"
    print(f"Fetching test case {index} from {api_url}...")
    repo_dir = os.path.join("D:\\ProgrammingProjekts\\ASEPublic\\repos", f"repo_{index}")  # Use unique repo directory per task
    start_dir = os.getcwd()  # Remember original working directory
    os.environ["REPO_NAME"] = f"repo_{index}"

    # Instantiate tools
    reader = FileReadTool()
    writer = FileWriterTool()
    dir_reader = DirectoryReadTool()

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
        if not os.path.isdir("D:\\ProgrammingProjekts\\ASEPublic\\repos"+ '\\' + os.environ.get('REPO_NAME', '')):
            subprocess.run(["git", "clone", repo_url, repo_dir], check=True, env=env)

        if checkout_part:
            commit_hash = checkout_part.split()[-1]
            print(f"Checking out commit: {commit_hash}")
            subprocess.run(["git", "checkout", commit_hash], cwd=repo_dir, check=True, env=env)

        print(f"Launching Agent-System (Crew AI)...")

        inputs = {
            'index': index,
            'problem_statement': prompt
        }
    
        try:
            os.environ["REPO_NAME"] = f"repo_{index}"


            tools = [reader, writer, dir_reader]

            mas = ASE(index, tools)
            mas.crew().kickoff(inputs=inputs)
        except Exception as e:
            raise Exception(f"An error occurred while running the crew: {e}")

        
        # Call REST service instead for evaluation changes from agent
        print(f"Calling SWE-Bench REST service with repo: {repo_dir}")
        test_payload = {
            "instance_id": instance_id,
            "repoDir": f"\\repo_{index}",  # mount with docker
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
            #log.write(f"Total Tokens Used: {token_total}\n")
        print(f"Test case {index} completed and logged.")
        # if not os.access(repo_dir, os.W_OK):
        #     os.chmod(repo_dir, stat.S_IWUSR)
        # os.system(f"rd /s /q \"{repo_dir}\"")

    except Exception as e:
        os.chdir(start_dir)
        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"\n--- TESTCASE {index} ---\n")
            log.write(f"Error: {e}\n")
        print(f"Error in test case {index}: {e}")
        # if not os.access(repo_dir, os.W_OK):
        #     os.chmod(repo_dir, stat.S_IWUSR)
        # os.system(f"rd /s /q \"{repo_dir}\"")


async def main():
    #for issue_nr in range(1,31):
        await handle_task(13)


if __name__ == "__main__":
    asyncio.run(main())                                        
import os
import re
from typing import List, Any

from langchain_core.tools import tool

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

WORKSPACE_ROOT = os.getenv('WORKSPACE_ROOT')

class OverwriteFileInput(BaseModel):
    file_path: str
    content: str

@tool(args_schema=OverwriteFileInput)
def overwrite_file(
        file_path: str,
        content: str
) -> str:
    """
    Create a new File with content or Overwrite an existing file with new content.

    Args:
        file_path (str): Path to the file.
        content (str): Content to write or append

    Returns:
        str: Result of the operation or the content of the file.
    """

   # file_path = f"{os.environ.get('WORKSPACE_ROOT')}/{os.environ.get('REPO_NAME')}/{file_path}"
    # Convert to absolute path if needed
    file_path = file_path.strip().strip('"').strip("'")

    if not os.path.isabs(file_path):
        file_path = os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), file_path)

    # Normalize the path
    file_path = os.path.normpath(file_path)

    git_dir = '.git'

    if git_dir in file_path:
        return f"Error: File '{file_path}' is inside forbidden dir"

    if is_in_git_dir(file_path):
        return f"Error: File '{file_path}' is inside forbidden dir"

    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' not found."



    try:
        with open(file_path, "w") as file:
            print(f"WRITE FILE {file_path}")
            file.write(content)
        return f"File {file_path} written successfully."
    except Exception as e:
        return f"An error occurred while writing to the file: {e}"


@tool
def find_and_replace(
        file_path: str,
        pattern: str,
        replacement: str
) -> str:
    """
    Allows to use search and replace writing operations via Regex expressions.

    Args:
        file_path (str): Path to the file.
        pattern (str): The regex pattern to replace
        replacement (str): Content to replace the pattern with.

    Returns:
        str: Result of the operation or the content of the file."""
    # Convert to absolute path if needed
    file_path = file_path.strip().strip('"').strip("'")

    if not os.path.isabs(file_path):
        file_path = os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), file_path)

    # Normalize the path
    file_path = os.path.normpath(file_path)

    git_dir = '.git'

    if git_dir in file_path:
        return f"Error: File '{file_path}' is inside forbidden dir"

    if is_in_git_dir(file_path):
        return f"Error: File '{file_path}' is inside forbidden dir"

    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' not found."
    try:
        with open(file_path, "r") as file:
            content = file.read()

        modified_content = re.sub(pattern, replacement, content)
        with open(file_path, "w") as file:
            file.write(modified_content)
    except Exception as e:
        return f"An error occurred while writing to the file: {e}"
    return f"FIND AND REPLACE in {file_path} successful!"


@tool
def list_files_in_repository() -> list[str]:
    """
    Lists all files in a given repository directory recursively.

    Returns:
        list: A list of file paths relative to the repository root, or an error message.
    """

    max_files: int = 500
    repo_path = f"{os.environ.get('WORKSPACE_ROOT')}/{os.environ.get('REPO_NAME')}"
    repo_path = os.path.normpath(repo_path)
    print(repo_path)
    try:
        if not os.path.exists(repo_path):
            return [f"Error: Repository path '{repo_path}' does not exist."]

        file_list = []
        for root, _, files in os.walk(repo_path):
            for file in files:
                # Construct the relative file path
                relative_path = os.path.relpath(os.path.join(root, file), repo_path)
                file_list.append(relative_path)
                if len(file_list) >= max_files:
                    return file_list

        return file_list
    except Exception as e:
        return [f"Error: An error occurred while listing files: {e}"]

class ReplaceStringInput(BaseModel):
    string_to_find: str
    replacement: str
    file_path: str

@tool(args_schema=ReplaceStringInput)
def replace_string(string_to_find : str, replacement : str, file_path : str):
    """
    Replace an occurrence of a string in a given file

    Args:
        string_to_find (str): the string which needs to be replaced
        replacement (str): the string to replace with
        file_path (str): the file in the repository this is the full path to the file from the repository root starting with no slash

    Returns:
        string: either success or failure, success if the replacement was successful and failure if was not.
    """

    print(f"trying to replace string \r\n {string_to_find} \r\n\r\n with  \r\n\r\n {replacement} \r\n in file {file_path}")
    try:
        with open(os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), file_path), "r") as file:
            content = file.read()

        modified_content = content.replace(string_to_find, replacement,1)
        with open(os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), file_path), "w") as file:
            file.write(modified_content)
    except Exception as e:
        print(f"failure on Error")
        return 'failure'
    if content == modified_content :
        print(f"failure no changes")
        return 'failure'
    print(f"success")
    return 'success'


class ListDirInput(BaseModel):
    path: str
    recursive: bool = False
    max_items: int = Field(default=50, description="Maximum number of items to return to avoid too much output.")

@tool(args_schema=ListDirInput)
def list_dir(path: str, recursive: bool = False, max_items: int = 50) -> List[str]:
    """
    List files and directories in the specified directory.
    Limits the number of results to avoid exceeding token limits.
    """


    if not os.path.isabs(path):
        repo_path = os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), path)
    else:
        repo_path = path

    repo_path = os.path.normpath(repo_path)

    if not os.path.exists(repo_path):
        return f"Directory not found: {repo_path}"


    paths = []
    if recursive:
        for root, dirs, files in os.walk(repo_path):
            for name in dirs + files:
                paths.append(os.path.join(root, name))
                if len(paths) >= max_items:
                    break
            if len(paths) >= max_items:
                break
    else:
        for name in os.listdir(repo_path):
            paths.append(os.path.join(repo_path, name))
            if len(paths) >= max_items:
                break

    return paths

@tool
def read_file(file_path: str) -> str:
    """
    Reads the content of a file and returns it as a string.

    Args:
        file_path (str): Path to the file to be read.

    Returns:
        str: Content of the file or an error message.
    """
    # Convert to absolute path if needed
    file_path = file_path.strip().strip('"').strip("'")

    if not os.path.isabs(file_path):
        file_path = os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), file_path)

    # Normalize the path
    file_path = os.path.normpath(file_path)

    git_dir = '.git'

    if git_dir in file_path:
        return f"Error: File '{file_path}' is inside forbidden dir"

    if is_in_git_dir(file_path):
        return f"Error: File '{file_path}' is inside forbidden dir"

    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' not found."

    try:
        with open(file_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except Exception as e:
        return f"Error: An error occurred while reading the file: {e}"


@tool
def delete_lines(file_path: str, start_line: int, end_line: int) -> None:
    """
    Delete a range of lines from a file.

    Parameters:
        file_path (str): Path to the target file.
        start_line (int): The starting line number (1-based index) of the range to delete.
        end_line (int): The ending line number (inclusive, 1-based index) of the range to delete.

    Raises:
        ValueError: If start_line or end_line are out of bounds or invalid.
        IOError: If the file cannot be read or written.
    """
    if start_line == 0:
        start_line += 1
    if end_line == 0:
        end_line += 1
        # Convert to absolute path if needed
    file_path = file_path.strip().strip('"').strip("'")

    if not os.path.isabs(file_path):
        file_path = os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), file_path)

    # Normalize the path
    file_path = os.path.normpath(file_path)

    git_dir = '.git'

    if git_dir in file_path:
        return f"Error: File '{file_path}' is inside forbidden dir"

    if is_in_git_dir(file_path):
        return f"Error: File '{file_path}' is inside forbidden dir"

    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' not found."

    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        raise ValueError("Invalid line range specified.")

    del lines[start_line - 1:end_line]

    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines(lines)


class InsertAtLineInput(BaseModel):
    file_path: str
    line_number: int
    content: str

@tool(args_schema=InsertAtLineInput)
def insert_at_line(file_path: str, line_number: int, content: str) -> str | None:
    """
    Insert a line of text at a specific position in a file.

    Parameters:
        file_path (str): Path to the target file.
        line_number (int): The line number (1-based index) at which to insert the new content.
        content (str): The content to insert into the file.

    Raises:
        ValueError: If line_number is out of bounds.
        IOError: If the file cannot be read or written.
    """
    if line_number == 0:
        line_number += 1
        # Convert to absolute path if needed
    file_path = file_path.strip().strip('"').strip("'")

    if not os.path.isabs(file_path):
        file_path = os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), file_path)

    # Normalize the path
    file_path = os.path.normpath(file_path)

    git_dir = '.git'

    if git_dir in file_path:
        return f"Error: File '{file_path}' is inside forbidden dir"

    if is_in_git_dir(file_path):
        return f"Error: File '{file_path}' is inside forbidden dir"

    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' not found."

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        if line_number < 1 or line_number > len(lines) + 1:
            raise ValueError("Invalid line number specified.")

        lines.insert(line_number - 1, content + '\n')

        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except Exception as e:
        return f"Error: An error occurred while reading the file: {e}"



def replace_lines(file_path: str, start_line: int, end_line: int, new_content: list[str]) -> str | None:
    """
    Replace a range of lines in a file with new content.

    Parameters:
        file_path (str): Path to the target file.
        start_line (int): The starting line number (1-based index) of the range to replace.
        end_line (int): The ending line number (inclusive, 1-based index) of the range to replace.
        new_content (list[str]): A list of strings to replace the specified lines.

    Raises:
        ValueError: If start_line or end_line are out of bounds or invalid.
        IOError: If the file cannot be read or written.
    """
    if start_line == 0:
        start_line += 1
    if end_line == 0:
        end_line += 1

    file_path = file_path.strip().strip('"').strip("'")

    if not os.path.isabs(file_path):
        file_path = os.path.join(os.environ.get('WORKSPACE_ROOT', ''),os.environ.get('REPO_NAME', ''), file_path)

    # Normalize the path
    file_path = os.path.normpath(file_path)

    git_dir = '.git'

    if git_dir in file_path:
        return f"Error: File '{file_path}' is inside forbidden dir"

    if is_in_git_dir(file_path):
        return f"Error: File '{file_path}' is inside forbidden dir"
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            raise ValueError("Invalid line range specified.")

        lines[start_line - 1:end_line] = [line + '\n' if not line.endswith('\n') else line for line in new_content]

        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except Exception as e:
        return f"Error: An error occurred while reading the file: {e}"

class ReplaceLinesInput(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    new_content: List[str]

replace_lines_tool = StructuredTool.from_function(
    func=replace_lines,
    args_schema=ReplaceLinesInput,
    description="""
    Replace a range of lines in a file with new content.

    Parameters:
        file_path (str): Path to the target file.
        start_line (int): The starting line number (1-based index) of the range to replace.
        end_line (int): The ending line number (inclusive, 1-based index) of the range to replace.
        new_content (list[str]): A list of strings to replace the specified lines.

    Raises:
        ValueError: If start_line or end_line are out of bounds or invalid.
        IOError: If the file cannot be read or written.
    """
)
def is_in_git_dir(path: str) -> bool:
    path = os.path.abspath(os.path.normpath(path))
    git_dir = os.path.abspath(os.path.normpath('git'))

    # Check if path is inside .git directory
    try:
        # commonpath returns the shared path prefix
        common = os.path.commonpath([path, git_dir])
        return common == git_dir
    except ValueError:
        # If paths are on different drives (Windows), commonpath throws ValueError
        return False
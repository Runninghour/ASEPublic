from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List


@CrewBase
class ASE():
    """ASE crew"""

    agents: List[BaseAgent]
    tasks: List[Task]
    
    def __init__(self, index, tools):
        self.index = index
        self.tools = tools


    @agent
    def planner(self) -> Agent:
        return Agent(
            config=self.agents_config['planner'], # type: ignore[index]
            verbose=True,
            max_tokens=100000,
            #tools=[list_files_in_repository]
            tools=[self.tools[0],self.tools[2]]
        )

    #[(0, 'read_file'), (1, 'read_multiple_files'), (2, 'write_file'), (3, 'edit_file'), (4, 'create_directory'), (5, 'list_directory'), (6, 'list_directory_with_sizes'), (7, 'directory_tree'), (8, 'move_file'), (9, 'search_files'), (10, 'get_file_info'), (11, 'list_allowed_directories')]
    @agent
    def coder(self) -> Agent:
        return Agent(
            config=self.agents_config['coder'], # type: ignore[index]
            verbose=True,
            max_tokens=100000,
            #tools=[read_file, find_and_replace, delete_lines, insert_at_line]
            tools=[self.tools[0],self.tools[1], self.tools[2]],
        )
    
    @agent
    def tester(self) -> Agent:
        return Agent(
            config=self.agents_config['coder'], # type: ignore[index]
            verbose=True,
            max_tokens=100000,
            #tools=[read_file]
            tools=[self.tools[0], self.tools[2]]
        )

    @task
    def planning_task(self) -> Task:
        return Task(
            config=self.tasks_config['planning_task'], # type: ignore[index]
        )

    @task
    def coding_task(self) -> Task:
        return Task(
            config=self.tasks_config['coding_task'], # type: ignore[index]
        )
    
    @task
    def testing_task(self) -> Task:
        return Task(
            config=self.tasks_config['testing_task'], # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the crew"""
        
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.hierarchical,
            verbose=True,
            manager_llm="gemini/gemini-2.0-flash",
        )

import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from datetime import datetime
from app.schemas import ArticleOut
from crewai_tools import TavilyResearchTool

from dotenv import load_dotenv
load_dotenv()  



llm = LLM(
    model = "openai/meta/llama-3.1-8b-instruct",
    base_url = "https://integrate.api.nvidia.com/v1",
    api_key = os.getenv("NVIDIA_API_KEY")
)

@CrewBase
class TheArticleCrew():
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def research_agent(self) -> Agent:
        return Agent(
            config = self.agents_config["research_agent"],
            tools = [TavilyResearchTool(
                citation_format = "numbered"
            )],
            reasoning = True,
            inject_date = True,
            llm = llm,
            max_rpm = 2
        )
    @agent
    def writer_agent(self) -> Agent:
        return Agent(
            config = self.agents_config["writer_agent"],
            llm = llm,
            max_rpm = 2
        )
    @agent
    def editor_agent(self) -> Agent:
        return Agent(
            config = self.agents_config["editor_agent"],
            llm = llm,
            max_rpm = 2
                     )

    @task
    def research_task(self) -> Task:
        return Task(
            config = self.tasks_config["research_task"],
            agent = self.research_agent()
        )
    @task
    def writer_task(self) -> Task:
        return Task(
            config= self.tasks_config["writer_task"],
            agent = self.writer_agent(),
            context = [self.research_task()],
            output_pydantic = ArticleOut
        )
    @task
    def editor_task(self) -> Task:
        return Task(
            config = self.tasks_config["editor_task"],
            agent = self.editor_agent(),
            context = [self.writer_task()],
            output_pydantic = ArticleOut
        )
    @crew
    def article_crew(self) -> Crew:
        return Crew(
            agents = self.agents,
            tasks = self.tasks,
            process = Process.sequential,
            planning = True,
            planning_llm=llm,
            max_rpm = 2
        )



async def generate_article(topic: str, current_date: str) -> str:
    """Generate an article using the CrewAI crew."""
    crew = TheArticleCrew()
    result = await crew.article_crew().kickoff_async(
        inputs={"topic": topic, "current_date": current_date}
    )
    return result.pydantic.model_dump()



from typing import Any, TypedDict
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph

from chains import get_finish_chain, get_supervisor_chain
from llms import get_llm
from prompts import (
    get_communication_agent_prompt_template,
    get_planning_agent_prompt_template,
    get_resource_agent_prompt_template,
    get_review_agent_prompt_template,
    get_task_analysis_agent_prompt_template,
)

load_dotenv()

WORKPLACE_PIPELINE = [
    "ResourceAgent",
    "PlanningAgent",
    "CommunicationAgent",
    "ReviewAgent",
]

VALID_AGENTS = [
    "TaskAnalysisAgent",
    "ResourceAgent",
    "PlanningAgent",
    "CommunicationAgent",
    "ReviewAgent",
    "ChatBot",
    "Finish",
]


def init_chat_model(state_config):
    return get_llm(
        provider=state_config["model_provider"],
        model=state_config["model"],
        dashscope_api_key=state_config.get("DASHSCOPE_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY"),
        api_key=state_config.get("DEEPSEEK_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or state_config.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY"),
        base_url=state_config.get("DEEPSEEK_BASE_URL")
        or os.environ.get("DEEPSEEK_BASE_URL")
        or state_config.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL"),
        temperature=state_config.get("temperature", 0.3),
    )


def _is_workplace_task(user_input: str) -> bool:
    text = user_input.lower()
    keywords = [
        "任务",
        "项目",
        "截止",
        "deadline",
        "计划",
        "执行",
        "汇报",
        "沟通",
        "协作",
        "风险",
        "会议",
        "方案",
        "role:",
        "task_description",
    ]
    return any(keyword in text for keyword in keywords)


def _set_followup_queue(state, queue):
    state["followup_queue"] = list(queue)
    state["needs_followup"] = ""


def _advance_or_finish(state):
    queue = state.get("followup_queue", [])
    if queue:
        state["needs_followup"] = queue.pop(0)
        state["followup_queue"] = queue
        state["task_completed"] = False
    else:
        state["needs_followup"] = ""
        state["task_completed"] = True
    return state


def _latest_agent_output(state, agent_name: str) -> str:
    for msg in reversed(state.get("messages", [])):
        if getattr(msg, "name", None) == agent_name:
            return msg.content
    return ""


def _append_agent_result(state, agent_name: str, result_content: str):
    state["messages"].append(AIMessage(content=result_content, name=agent_name))
    return _advance_or_finish(state)


def supervisor_node(state):
    """Supervisor node that preserves the multi-agent dispatch loop."""
    chat_history = state.get("messages", [])
    user_query = state.get("user_input", "")

    if state.get("needs_followup"):
        next_action = state["needs_followup"]
        state["needs_followup"] = ""
        state["next_step"] = next_action
        print(f"执行后续任务: {next_action}")
        return state

    if not chat_history:
        chat_history.append(HumanMessage(content=user_query))

    if _is_workplace_task(user_query):
        _set_followup_queue(state, WORKPLACE_PIPELINE)
        next_action = "TaskAnalysisAgent"
    else:
        llm = init_chat_model(state["config"])
        supervisor_chain = get_supervisor_chain(llm)
        output = supervisor_chain.invoke({"messages": chat_history})
        next_action = output.content.strip()
        if next_action not in VALID_AGENTS:
            next_action = "ChatBot"

    print(f"路由到: {next_action}")
    state["next_step"] = next_action
    state["messages"] = chat_history
    return state


def task_analysis_node(state):
    llm = init_chat_model(state["config"])
    agent = create_agent(
        llm,
        [],
        system_prompt=get_task_analysis_agent_prompt_template(),
    )
    state["callback"].write_agent_name("TaskAnalysisAgent 任务分析")
    result = agent.invoke({"messages": state["messages"]})
    return _append_agent_result(state, "TaskAnalysisAgent", result["messages"][-1].content)


def resource_node(state):
    llm = init_chat_model(state["config"])
    agent = create_agent(
        llm,
        # Current workplace-task flow is offline by default.
        # Future: add [get_google_search_results, scrape_website] here when
        # ResourceAgent must perform live web research or URL-based analysis.
        [],
        system_prompt=get_resource_agent_prompt_template(),
    )
    state["callback"].write_agent_name("ResourceAgent 资源分析")
    result = agent.invoke({"messages": state["messages"]})
    return _append_agent_result(state, "ResourceAgent", result["messages"][-1].content)


def planning_node(state):
    llm = init_chat_model(state["config"])
    agent = create_agent(
        llm,
        [],
        system_prompt=get_planning_agent_prompt_template(),
    )
    state["callback"].write_agent_name("PlanningAgent 执行计划生成")
    result = agent.invoke({"messages": state["messages"]})
    return _append_agent_result(state, "PlanningAgent", result["messages"][-1].content)


def communication_node(state):
    llm = init_chat_model(state["config"])
    agent = create_agent(
        llm,
        [],
        system_prompt=get_communication_agent_prompt_template(),
    )
    state["callback"].write_agent_name("CommunicationAgent 沟通文本生成")
    result = agent.invoke({"messages": state["messages"]})
    return _append_agent_result(
        state, "CommunicationAgent", result["messages"][-1].content
    )


def review_node(state):
    llm = init_chat_model(state["config"])
    agent = create_agent(
        llm,
        [],
        system_prompt=get_review_agent_prompt_template(),
    )
    state["callback"].write_agent_name("ReviewAgent 风险复核与优化")

    synthesis_prompt = f"""请整合以下信息，输出最终职场任务处理方案。

用户原始输入：
{state.get("user_input", "")}

任务分析：
{_latest_agent_output(state, "TaskAnalysisAgent")}

资源分析：
{_latest_agent_output(state, "ResourceAgent")}

执行计划：
{_latest_agent_output(state, "PlanningAgent")}

沟通文本：
{_latest_agent_output(state, "CommunicationAgent")}"""

    messages = state["messages"] + [HumanMessage(content=synthesis_prompt)]
    result = agent.invoke({"messages": messages})
    state["messages"].append(AIMessage(content=result["messages"][-1].content, name="ReviewAgent"))
    state["task_completed"] = True
    state["needs_followup"] = ""
    state["followup_queue"] = []
    return state


def chatbot_node(state):
    llm = init_chat_model(state["config"])
    state["callback"].write_agent_name("ChatBot")
    finish_chain = get_finish_chain(llm)
    output = finish_chain.invoke({"messages": state["messages"]})
    state["messages"].append(AIMessage(content=output.content, name="ChatBot"))
    state["task_completed"] = True
    return state


def define_graph():
    """Define the workplace task multi-agent workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("TaskAnalysisAgent", task_analysis_node)
    workflow.add_node("ResourceAgent", resource_node)
    workflow.add_node("PlanningAgent", planning_node)
    workflow.add_node("CommunicationAgent", communication_node)
    workflow.add_node("ReviewAgent", review_node)
    workflow.add_node("ChatBot", chatbot_node)

    workflow.set_entry_point("Supervisor")

    workflow.add_conditional_edges(
        "Supervisor",
        lambda x: x["next_step"],
        {
            "TaskAnalysisAgent": "TaskAnalysisAgent",
            "ResourceAgent": "ResourceAgent",
            "PlanningAgent": "PlanningAgent",
            "CommunicationAgent": "CommunicationAgent",
            "ReviewAgent": "ReviewAgent",
            "ChatBot": "ChatBot",
            "Finish": END,
        },
    )

    def should_continue(state):
        return "END" if state.get("task_completed", True) else "CONTINUE"

    for agent in [
        "TaskAnalysisAgent",
        "ResourceAgent",
        "PlanningAgent",
        "CommunicationAgent",
        "ReviewAgent",
        "ChatBot",
    ]:
        workflow.add_conditional_edges(
            agent,
            should_continue,
            {
                "END": END,
                "CONTINUE": "Supervisor",
            },
        )

    return workflow.compile()


class AgentState(TypedDict):
    user_input: str
    messages: list[BaseMessage]
    next_step: str
    config: dict
    callback: Any
    task_completed: bool
    needs_followup: str
    followup_queue: list[str]

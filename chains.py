from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from members import get_team_members_details
from prompts import get_finish_step_prompt, get_supervisor_prompt_template


def get_supervisor_chain(llm: BaseChatModel):
    team_members = get_team_members_details()
    formatted_members = "\n\n".join(
        f"**{idx + 1}. {member['name']}**\nRole: {member['description']}"
        for idx, member in enumerate(team_members)
    )
    options = [member["name"] for member in team_members]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", get_supervisor_prompt_template()),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                f"""Given the conversation above, who should act next?
Select EXACTLY ONE of: {options}

Rules:
- New workplace task: TaskAnalysisAgent
- Resource or dependency analysis: ResourceAgent
- Plan, timeline, execution steps: PlanningAgent
- Communication or reporting content: CommunicationAgent
- Risk review or final integrated plan: ReviewAgent
- General chat or formatting: ChatBot
- When done: Finish

Respond with ONLY the agent name, nothing else.""",
            ),
        ]
    ).partial(options=str(options), members=formatted_members)

    return prompt | llm


def get_finish_chain(llm: BaseChatModel):
    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="messages"),
            ("system", get_finish_step_prompt()),
        ]
    )
    return prompt | llm

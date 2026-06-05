from typing import Literal

from pydantic import BaseModel, Field


class RouteSchema(BaseModel):
    next_action: Literal[
        "TaskAnalysisAgent",
        "ResourceAgent",
        "PlanningAgent",
        "CommunicationAgent",
        "ReviewAgent",
        "ChatBot",
        "Finish",
    ] = Field(..., title="Next", description="Select the next role")


class WorkplaceTaskInput(BaseModel):
    task_description: str = Field(description="用户输入的职场任务描述")
    project_context: str = Field(description="项目背景、业务上下文或相关约束")
    deadline: str = Field(description="任务截止时间或期望完成节奏")
    role: str = Field(description="用户在任务中的角色、职责或汇报对象")


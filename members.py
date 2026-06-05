def get_team_members_details() -> list[dict]:
    """Return the workplace task agent roster used by the supervisor."""
    return [
        {
            "name": "TaskAnalysisAgent",
            "description": "分析职场任务目标、交付物、关键要求、约束条件和成功标准。",
        },
        {
            "name": "ResourceAgent",
            "description": "梳理完成任务所需的信息、资源、依赖方、工具和缺口。",
        },
        {
            "name": "PlanningAgent",
            "description": "将任务拆解为可执行步骤，并生成时间安排和优先级。",
        },
        {
            "name": "CommunicationAgent",
            "description": "生成沟通、汇报、协作请求和对齐事项的建议文案。",
        },
        {
            "name": "ReviewAgent",
            "description": "复核方案风险、优化建议，并按最终模板整合完整工作方案。",
        },
        {
            "name": "ChatBot",
            "description": "处理一般职场问答、解释和格式调整。",
        },
        {
            "name": "Finish",
            "description": "表示工作流结束。",
        },
    ]

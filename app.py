from typing import Callable, TypeVar
import inspect
import json
import os
import threading

import streamlit as st
from dotenv import load_dotenv
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from langchain_core.messages import HumanMessage
from streamlit.delta_generator import DeltaGenerator
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from agents import define_graph
from custom_callback_handler import CustomStreamlitCallbackHandler

load_dotenv()

CONFIG_FILE = "temp/app_config.json"


def load_persistent_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print(f"加载配置文件失败: {exc}")
    return {}


def save_persistent_config(config):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        print(f"保存配置文件失败: {exc}")
        return False


def get_secret(key, default=""):
    val = os.getenv(key)
    if val is not None:
        return val
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


st.set_page_config(
    page_title="WorkAgent-MultiAgent 职场任务助手",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    h1 { color: #1f77b4; font-weight: 650; }
    [data-testid="stSidebar"] { background-color: #f8f9fa; }
    .stButton>button { border-radius: 8px; font-weight: 500; }
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea { border-radius: 8px; font-size: 14px; }
    .stSuccess, .stWarning, .stError, .stInfo { border-radius: 8px; padding: 10px; font-size: 14px; }
</style>
""",
    unsafe_allow_html=True,
)

os.makedirs("temp", exist_ok=True)
persistent_config = load_persistent_config()

st.sidebar.title("系统配置")
st.sidebar.info("场景已切换为：职场任务处理。系统会按多智能体流程生成工作方案。")

if "saved_model_name" not in st.session_state:
    st.session_state["saved_model_name"] = (
        persistent_config.get("model_name") or get_secret("MODEL_NAME") or "qwen-plus"
    )
if "saved_api_key" not in st.session_state:
    st.session_state["saved_api_key"] = (
        persistent_config.get("api_key")
        or get_secret("OPENAI_API_KEY")
        or get_secret("DASHSCOPE_API_KEY")
        or ""
    )
if "saved_base_url" not in st.session_state:
    st.session_state["saved_base_url"] = (
        persistent_config.get("base_url")
        or get_secret("OPENAI_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
if "saved_temperature" not in st.session_state:
    st.session_state["saved_temperature"] = persistent_config.get("temperature", 0.3)
if "saved_serper_key" not in st.session_state:
    st.session_state["saved_serper_key"] = (
        persistent_config.get("serper_key") or get_secret("SERPER_API_KEY") or ""
    )
if "saved_firecrawl_key" not in st.session_state:
    st.session_state["saved_firecrawl_key"] = (
        persistent_config.get("firecrawl_key") or get_secret("FIRECRAWL_API_KEY") or ""
    )

with st.sidebar.expander("模型参数设置", expanded=True):
    model_preset = st.selectbox(
        "选择预设模型",
        ["自定义", "qwen-plus", "qwen-max", "qwen-turbo", "gpt-4", "gpt-3.5-turbo", "deepseek-chat"],
    )
    if model_preset != "自定义":
        default_model = model_preset
        if model_preset.startswith("qwen"):
            default_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        elif model_preset.startswith("gpt"):
            default_base_url = "https://api.openai.com/v1"
        elif model_preset == "deepseek-chat":
            default_base_url = "https://api.deepseek.com/v1"
        else:
            default_base_url = st.session_state["saved_base_url"]
    else:
        default_model = st.session_state["saved_model_name"]
        default_base_url = st.session_state["saved_base_url"]

    model_name = st.text_input("模型名称", value=default_model)
    api_key = st.text_input("API Key", value=st.session_state["saved_api_key"], type="password")
    base_url = st.text_input("API Base URL", value=default_base_url)
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=float(st.session_state["saved_temperature"]),
        step=0.1,
    )

    if st.button("保存模型配置", use_container_width=True):
        st.session_state["saved_model_name"] = model_name
        st.session_state["saved_api_key"] = api_key
        st.session_state["saved_base_url"] = base_url
        st.session_state["saved_temperature"] = temperature
        ok = save_persistent_config(
            {
                "model_name": model_name,
                "api_key": api_key,
                "base_url": base_url,
                "temperature": temperature,
                "serper_key": st.session_state.get("saved_serper_key", ""),
                "firecrawl_key": st.session_state.get("saved_firecrawl_key", ""),
            }
        )
        st.success("配置已保存") if ok else st.error("配置保存失败")

settings = {
    "model": model_name,
    "model_provider": "openai",
    "temperature": temperature,
    "OPENAI_API_KEY": api_key,
    "OPENAI_BASE_URL": base_url,
}

# Search and scraping are intentionally disabled in the current workplace-task flow.
# Current scope: TaskAnalysisAgent -> ResourceAgent -> PlanningAgent ->
# CommunicationAgent -> ReviewAgent all run on the LLM context supplied by the user.
# Future scenarios to re-enable this block:
# - ResourceAgent needs live market, policy, competitor, vendor, or industry research.
# - ReviewAgent must validate facts against external sources before final delivery.
# - The user asks for URL-based analysis or webpage summarization.
# Re-enable by restoring the sidebar inputs below and adding the tools back to
# ResourceAgent in agents.py: [get_google_search_results, scrape_website].
serper_api_key = ""
firecrawl_api_key = ""
st.sidebar.caption("搜索/网页抓取服务：当前主流程未启用，仅在需要联网资料核验时开启。")

st.sidebar.markdown("---")
if api_key and base_url:
    st.sidebar.success(f"当前模型：{model_name}")
else:
    st.sidebar.error("请先配置模型 API Key 和 Base URL")

st.title("WorkAgent-MultiAgent 职场任务助手")
st.markdown(
    """
基于 LangGraph 的多智能体职场任务处理系统。流程如下：

```mermaid
flowchart TD
    A[用户输入工作任务] --> B[TaskAnalysisAgent 任务分析]
    A --> I1[task_description]
    A --> I2[project_context]
    A --> I3[deadline]
    A --> I4[role]
    B --> C[ResourceAgent 资源分析]
    C --> D[PlanningAgent 执行计划生成]
    D --> E[CommunicationAgent 沟通文本生成]
    E --> F[ReviewAgent 风险复核与优化]
    F --> G[最终输出工作方案]
    G --> O1[任务目标分析]
    G --> O2[关键需求与限制]
    G --> O3[执行步骤]
    G --> O4[时间安排]
    G --> O5[沟通/汇报内容]
    G --> O6[风险与优化建议]
```
"""
)

flow_graph = define_graph()
message_history = StreamlitChatMessageHistory()

if "user_query_history" not in st.session_state:
    st.session_state["user_query_history"] = []
if "response_history" not in st.session_state:
    st.session_state["response_history"] = []
if "is_processing" not in st.session_state:
    st.session_state["is_processing"] = False
if "stop_execution" not in st.session_state:
    st.session_state["stop_execution"] = False
if "input_key" not in st.session_state:
    st.session_state["input_key"] = 0

st.sidebar.markdown("---")
st.sidebar.caption("关闭浏览器页面不会停止本地 Streamlit 服务。")
if st.sidebar.button(
    "停止本地服务",
    use_container_width=True,
    disabled=st.session_state["is_processing"],
):
    st.sidebar.warning("正在停止本地服务，请稍后关闭页面。")
    threading.Timer(0.5, lambda: os._exit(0)).start()
    st.stop()


def initialize_callback_handler(main_container: DeltaGenerator):
    V = TypeVar("V")

    def wrap_function(func: Callable[..., V]) -> Callable[..., V]:
        context = get_script_run_ctx()

        def wrapped(*args, **kwargs) -> V:
            add_script_run_ctx(ctx=context)
            return func(*args, **kwargs)

        return wrapped

    streamlit_callback_instance = CustomStreamlitCallbackHandler(
        parent_container=main_container
    )
    for method_name, method in inspect.getmembers(
        streamlit_callback_instance, predicate=inspect.ismethod
    ):
        setattr(streamlit_callback_instance, method_name, wrap_function(method))
    return streamlit_callback_instance


def execute_chat_conversation(user_input, graph):
    callback_handler = initialize_callback_handler(st.container())
    st.session_state["is_processing"] = True
    try:
        callback_handler.clear_agent_sequence()
        output = graph.invoke(
            {
                "messages": list(message_history.messages)
                + [HumanMessage(content=user_input)],
                "user_input": user_input,
                "config": settings,
                "callback": callback_handler,
                "task_completed": False,
                "needs_followup": "",
                "followup_queue": [],
            },
            {"recursion_limit": 20},
        )

        agent_sequence = callback_handler.get_agent_sequence()
        if agent_sequence:
            emoji_map = {
                "TaskAnalysisAgent": "🔎",
                "ResourceAgent": "📚",
                "PlanningAgent": "🗓️",
                "CommunicationAgent": "✉️",
                "ReviewAgent": "✅",
                "ChatBot": "💬",
            }
            st.markdown("**Agent 执行顺序:**")
            st.markdown(
                " -> ".join(
                    f"{next((emoji for key, emoji in emoji_map.items() if key in agent), '⚙️')} {agent}"
                    for agent in agent_sequence
                )
            )

        messages_list = output.get("messages", [])
        message_history.clear()
        message_history.add_messages(messages_list)
        st.session_state["is_processing"] = False
        return messages_list[-1].content if messages_list else "未生成结果，请重试。"
    except Exception as exc:
        st.session_state["is_processing"] = False
        st.error(f"执行错误: {exc}")
        return "抱歉，执行过程中发生错误。请检查模型配置后重试。"


def enqueue_task(user_input):
    st.session_state["user_query_history"].append(user_input)
    st.session_state["response_history"].append("正在生成职场任务方案...")
    st.session_state["is_processing"] = True
    st.session_state["input_key"] += 1
    st.rerun()


col1, col2 = st.columns([6, 1])
with col2:
    if st.button("清空对话", use_container_width=True):
        st.session_state["user_query_history"] = []
        st.session_state["response_history"] = []
        st.session_state["is_processing"] = False
        message_history.clear()
        st.rerun()

with st.form("task_form", clear_on_submit=False):
    st.markdown("### 输入职场任务")
    task_description = st.text_area(
        "task_description",
        placeholder="任务描述，例如：下周三前完成季度经营复盘汇报，并给管理层提出下一季度改进计划。",
        height=110,
    )
    project_context = st.text_area(
        "project_context",
        placeholder="工作内容，例如：本季度新客增长放缓，销售团队反馈线索质量下降，老板希望看到数据原因和行动方案。",
        height=90,
    )
    c1, c2 = st.columns(2)
    with c1:
        deadline = st.text_input("deadline", placeholder="例如：下周三 18:00 前")
    with c2:
        role = st.text_input("role", placeholder="例如：运营经理，需要向 VP 汇报")

    submitted = st.form_submit_button("生成工作方案", disabled=st.session_state["is_processing"])
    if submitted:
        if not api_key or not base_url:
            st.error("请先配置模型 API Key 和 Base URL。")
        elif not task_description.strip():
            st.error("请至少填写 task_description。")
        else:
            formatted_input = f"""用户输入工作任务

task_description:
{task_description.strip()}

project_context:
{project_context.strip() or "未提供"}

deadline:
{deadline.strip() or "未提供"}

role:
{role.strip() or "未提供"}"""
            enqueue_task(formatted_input)

st.markdown("### 快捷任务")
quick_tasks = [
    "为一次跨部门项目延期问题生成处理方案",
    "为月度经营复盘准备执行计划和汇报内容",
    "为客户投诉升级设计沟通与风险处理方案",
    "为新产品上线前的准备工作生成任务拆解",
]
quick_cols = st.columns(4)
for idx, item in enumerate(quick_tasks):
    with quick_cols[idx]:
        if st.button(item, key=f"quick_{idx}", use_container_width=True, disabled=st.session_state["is_processing"]):
            if not api_key or not base_url:
                st.error("请先配置模型 API Key 和 Base URL。")
            else:
                enqueue_task(
                    f"""用户输入工作任务

task_description:
{item}

project_context:
需根据常见职场场景补全合理假设，并标注需要用户确认的信息。

deadline:
未提供

role:
任务负责人"""
                )

follow_up = st.chat_input(
    "也可以继续输入补充要求，例如：把时间安排压缩到 3 天内",
    disabled=st.session_state["is_processing"],
    key=f"chat_input_{st.session_state['input_key']}",
)
if follow_up:
    if not api_key or not base_url:
        st.error("请先配置模型 API Key 和 Base URL。")
    else:
        enqueue_task(follow_up)

if st.session_state["response_history"]:
    st.markdown("### 对话记录")
    for i, response in enumerate(st.session_state["response_history"]):
        with st.chat_message("user"):
            st.markdown(st.session_state["user_query_history"][i])

        if response == "正在生成职场任务方案...":
            with st.spinner("多智能体正在协作处理..."):
                chat_output = execute_chat_conversation(
                    st.session_state["user_query_history"][i], flow_graph
                )
                st.session_state["response_history"][i] = chat_output
                st.rerun()
        else:
            with st.chat_message("assistant"):
                st.markdown(response)

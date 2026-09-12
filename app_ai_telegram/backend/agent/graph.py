import asyncio
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, ToolMessage
from backend.config import settings
from backend.agent.state import AgentState
from backend.agent.prompts import SYSTEM_PROMPT

# Import công cụ
from backend.tools.web_search import web_search
from backend.tools.azure_tools import aca_get_service_status, aca_scale_app
from backend.tools.file_tools import list_files, read_file, write_file

ALL_TOOLS = [
    web_search,
    aca_get_service_status,
    aca_scale_app,
    list_files,
    read_file,
    write_file
]

def create_agent_graph():
    """Khởi tạo StateGraph LangGraph cho AI Agent."""
    llm = ChatOpenAI(
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        model=settings.OPENROUTER_MODEL,
        temperature=0.2,
        streaming=True,
        timeout=35.0,
        max_retries=2
    )
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    async def call_model(state: AgentState):
        messages = list(state["messages"])
        if not any(isinstance(m, SystemMessage) for m in messages):
            system_msg = state.get("system_prompt") or SYSTEM_PROMPT
            messages = [SystemMessage(content=system_msg)] + messages

        chunk_list = []
        async for chunk in llm_with_tools.astream(messages):
            chunk_list.append(chunk)

        if not chunk_list:
            raise RuntimeError("LLM không phản hồi.")

        full_response = chunk_list[0]
        for c in chunk_list[1:]:
            full_response = full_response + c

        return {
            "messages": [full_response],
            "step_count": state.get("step_count", 0) + 1
        }

    async def execute_tools(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        tools_map = {t.name: t for t in ALL_TOOLS}

        async def run_one(tc):
            t_name = tc["name"]
            t_args = tc["args"]
            t_id = tc["id"]
            tool_obj = tools_map.get(t_name)
            if tool_obj:
                try:
                    res = await tool_obj.ainvoke(t_args)
                except Exception as e:
                    res = f"Lỗi chạy công cụ {t_name}: {e}"
            else:
                res = f"Công cụ {t_name} không tồn tại."
            return ToolMessage(content=str(res), name=t_name, tool_call_id=t_id)

        results = await asyncio.gather(*(run_one(tc) for tc in tool_calls))
        return {"messages": results}

    def should_continue(state: AgentState):
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            if state.get("step_count", 0) >= settings.MAX_AGENT_STEPS:
                return "end"
            return "tools"
        return "end"

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", execute_tools)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()

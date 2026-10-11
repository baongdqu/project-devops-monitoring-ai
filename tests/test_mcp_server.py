# -*- coding: utf-8 -*-
from mcp_server.devops_mcp_server import list_tools, call_tool


def test_mcp_list_tools():
    tools = list_tools()
    tool_names = [t["name"] for t in tools]
    assert "aca_deploy_url_shortener" in tool_names
    assert "aca_get_service_status" in tool_names
    assert "aca_scale_app" in tool_names
    assert "aca_destroy_infra" in tool_names
    assert len(tools) == 4


def test_mcp_call_unknown_tool():
    res = call_tool("unknown_tool_xyz", {})
    assert "[Error]" in res

import os
from langchain_core.tools import tool
from backend.config import settings
from tavily import TavilyClient

@tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    Tìm kiếm thông tin trên internet bằng Tavily API.
    Dùng khi cần tra cứu tin tức, sự kiện mới, tài liệu hoặc thông tin thời gian thực.
    """
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        return "Lỗi: Chưa cấu hình TAVILY_API_KEY."
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results)
        results = response.get("results", [])
        if not results:
            return f"Không tìm thấy kết quả cho '{query}'."
        formatted = []
        for idx, item in enumerate(results, 1):
            formatted.append(f"[{idx}] {item.get('title', 'Không tiêu đề')}\nURL: {item.get('url', '#')}\n{item.get('content', '')}\n")
        return "\n".join(formatted)
    except Exception as e:
        return f"Lỗi tra cứu web: {str(e)}"

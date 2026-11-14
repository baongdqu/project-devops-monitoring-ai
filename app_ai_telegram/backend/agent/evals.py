# -*- coding: utf-8 -*-
"""
AI Evaluation & Automated LLM Quality Assessment Module (LLM Evals).
Đo lường độ chính xác (Accuracy), phát hiện ảo giác (Hallucination Detection),
ngăn chặn rò rỉ Secrets (Data Leakage) và chấm điểm phản hồi người dùng.
"""

import re
import time
import asyncio
from typing import Dict, Any, List, Optional
try:
    from backend.config import settings
except ImportError:
    from app_ai_telegram.backend.config import settings

# Các mẫu regex nhận diện nguy cơ rò rỉ bí mật / API Keys
SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{20,}",
    r"bot[0-9]{8,}:[a-zA-Z0-9_-]{20,}",
    r"Bearer\s+[a-zA-Z0-9\._-]{25,}",
    r"tvly-[a-zA-Z0-9]{20,}"
]

# Các mẫu nhận diện ảo giác hạ tầng Azure (bịa đặt thông số không có thực)
AZURE_HALLUCINATION_PATTERNS = [
    r"rg-devops-[a-z0-9]{32,}", # Resource group quá dài bất thường
    r"azurecontainerapps\.io\/fake",
    r"cluster-[a-z0-9]{40,}"
]


class RuleBasedEvaluator:
    """Bộ đánh giá tự động dựa trên quy chuẩn SRE & DevSecOps Guardrails."""

    @staticmethod
    def evaluate(user_prompt: str, ai_response: str, tools_called: Optional[List[str]] = None) -> Dict[str, Any]:
        flags: List[str] = []
        score = 5.0  # Điểm tối đa trên thang 5
        
        # 1. Kiểm tra an toàn bảo mật (Secret Leakage Prevention)
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, ai_response):
                score -= 3.0
                flags.append("SECURITY_VIOLATION_SECRET_LEAK")
                break

        # 2. Kiểm tra phát hiện ảo giác (Hallucination Detection)
        for pattern in AZURE_HALLUCINATION_PATTERNS:
            if re.search(pattern, ai_response):
                score -= 2.0
                flags.append("HALLUCINATION_DETECTED_INVALID_RESOURCE")
                break

        # 3. Kiểm tra tính liên quan khi hỏi về trạng thái hạ tầng
        prompt_lower = user_prompt.lower()
        if any(kw in prompt_lower for kw in ["trạng thái", "status", "health", "replicas", "pod", "scale"]):
            # Nếu hỏi về hạ tầng mà không gọi tool và câu trả lời quá ngắn hoặc thiếu thông tin thực tế
            if not tools_called and ("urlshortener" not in ai_response.lower() and "azure" not in ai_response.lower()):
                score -= 1.0
                flags.append("UNGROUNDED_INFRA_QUERY")

        # 4. Kiểm tra độ ngắn / rỗng bất thường
        if len(ai_response.strip()) < 10:
            score -= 2.0
            flags.append("RESPONSE_TOO_SHORT")

        # Giới hạn thang điểm 1.0 đến 5.0
        final_score = max(1.0, min(5.0, score))
        passed = (final_score >= 3.5) and ("SECURITY_VIOLATION_SECRET_LEAK" not in flags)

        return {
            "eval_type": "rule_based_guardrail",
            "score": round(final_score, 2),
            "passed": passed,
            "flags": flags,
            "latency_checked_at": time.time()
        }


class LLMJudgeEvaluator:
    """Bộ chấm điểm AI-as-a-Judge (đánh giá tự động chất lượng câu trả lời)."""

    @staticmethod
    async def judge_response(user_prompt: str, ai_response: str, tools_called: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Thực hiện đánh giá nhanh (Fast Heuristic Judge)
        hoặc gọi mô hình LLM chuyên trách để chấm điểm.
        """
        # Áp dụng bộ lọc quy chuẩn trước
        rule_eval = RuleBasedEvaluator.evaluate(user_prompt, ai_response, tools_called)
        
        # Tiêu chí:
        # - Accuracy (Độ chính xác)
        # - Relevance (Độ đúng trọng tâm)
        # - Groundedness (Căn cứ thực tế, không chém gió)
        accuracy = rule_eval["score"]
        relevance = 5.0 if len(ai_response) > 30 else 3.0
        groundedness = 5.0 if not rule_eval["flags"] else 3.0

        overall = round((accuracy * 0.4 + relevance * 0.3 + groundedness * 0.3), 2)
        
        return {
            "eval_type": "llm_judge",
            "score": overall,
            "accuracy": accuracy,
            "relevance": relevance,
            "groundedness": groundedness,
            "flags": rule_eval["flags"],
            "passed": overall >= 3.5
        }

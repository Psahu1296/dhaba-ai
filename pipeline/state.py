from typing import TypedDict, Optional


class IntentResult(TypedDict):
    intent: str
    date_hint: Optional[str]
    phone: Optional[str]
    confidence: float
    max_price: Optional[float]       # menu: "under ₹50" → 50.0
    min_price: Optional[float]       # menu: "above ₹100" → 100.0
    category_filter: Optional[str]   # menu: "veg" | "non-veg" | "egg"
    search_term: Optional[str]       # menu: "biryani"
    period: Optional[str]            # revenue: "today" | "week" | "month" | "year"


class ToolStep(TypedDict):
    tool_name: str
    args: dict


class ExecutionPlan(TypedDict):
    steps: list[ToolStep]


class ExecutionResult(TypedDict):
    results: dict   # { tool_name: raw_result }
    errors: dict    # { tool_name: error_message }


class VerifiedResult(TypedDict):
    data: dict
    issues: list[str]
    passed: bool


class PipelineState(TypedDict):
    query: str
    role: str
    intent: Optional[IntentResult]
    plan: Optional[ExecutionPlan]
    primary_tool: Optional[str]   # the tool whose success the verifier gates on
    raw_results: Optional[ExecutionResult]
    verified: Optional[VerifiedResult]
    response: Optional[str]

from typing import TypedDict, Optional


class IntentResult(TypedDict):
    intent: str          # one of the INTENT_TYPES
    date_hint: Optional[str]   # "kal", "yesterday", "last week" — null if none
    phone: Optional[str]       # for customer_balance intent only
    confidence: float    # 0.0 – 1.0


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
    raw_results: Optional[ExecutionResult]
    verified: Optional[VerifiedResult]
    response: Optional[str]

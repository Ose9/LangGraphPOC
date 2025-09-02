from typing import TypedDict, Annotated, Literal
from uuid import uuid4

from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# -------- Tools (mocked for a quick POC) --------
DATA = [
    {"sku": "A-101", "revenue": 900,  "cogs": 1200, "qty": 18, "category": "Apparel"},
    {"sku": "B-202", "revenue": 1600, "cogs": 1400, "qty": 25, "category": "Apparel"},
    {"sku": "C-303", "revenue": 700,  "cogs": 950,  "qty": 10, "category": "Accessories"},
    {"sku": "D-404", "revenue": 3000, "cogs": 2900, "qty": 60, "category": "Footwear"},
]

@tool
def fetch_margin_anomalies(days: int = 30, min_loss: int = 500) -> dict:
    """
    Return SKUs with negative profit whose absolute loss >= min_loss in the last `days`.
    """
    anomalies = []
    for row in DATA:
        profit = row["revenue"] - row["cogs"]
        if profit < 0 and abs(profit) >= min_loss:
            anomalies.append({
                "sku": row["sku"],
                "loss": abs(profit),
                "qty": row["qty"],
                "category": row["category"],
            })
    total_loss = sum(x["loss"] for x in anomalies)
    return {"days": days, "min_loss": min_loss, "count": len(anomalies),
            "total_loss": total_loss, "items": anomalies}

@tool
def raise_ticket(summary: str, severity: str = "medium") -> str:
    """
    Open a ticket in Ops/Finance system (stub). Returns a ticket ID.
    """
    ticket_id = f"TKT-{uuid4().hex[:6].upper()}"
    return f"{ticket_id} | severity={severity} | {summary}"

# -------- Agents --------
analyst_tools = [fetch_margin_anomalies]
finance_tools = [raise_ticket]

analyst_llm = ChatOpenAI(model="gpt-4o-mini").bind_tools(analyst_tools)
finance_llm = ChatOpenAI(model="gpt-4o-mini").bind_tools(finance_tools)

class State(TypedDict):
    messages: Annotated[list, add_messages]

def call_analyst(state: State):
    system = (
        "You are a Data Analyst. Use tools to get margin anomalies. "
        "If total_loss <= 500, conclude with 'FINAL:' and a brief summary. "
        "If total_loss > 500, summarize and ask Finance to decide, do not use 'FINAL:' yet."
    )
    msgs = [("system", system)] + state["messages"]
    resp = analyst_llm.invoke(msgs)
    return {"messages": [resp]}

def call_finance(state: State):
    system = (
        "You are a Finance Partner. If escalation is warranted, call raise_ticket with a short summary. "
        "Then conclude with 'FINAL:' and what you did. If not, just respond with 'FINAL:' and your rationale."
    )
    msgs = [("system", system)] + state["messages"]
    resp = finance_llm.invoke(msgs)
    return {"messages": [resp]}

def route_from_analyst(state: State) -> Literal["analyst_tools", "finance", "END"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "analyst_tools"
    content = getattr(last, "content", "")
    return "END" if "FINAL:" in content else "finance"

def route_from_finance(state: State) -> Literal["finance_tools", "analyst", "END"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "finance_tools"
    content = getattr(last, "content", "")
    return "END" if "FINAL:" in content else "analyst"

# -------- Graph --------
g = StateGraph(State)
g.add_node("analyst", call_analyst)
g.add_node("analyst_tools", ToolNode(analyst_tools))
g.add_node("finance", call_finance)
g.add_node("finance_tools", ToolNode(finance_tools))

g.add_edge(START, "analyst")
g.add_conditional_edges("analyst", route_from_analyst,
                        {"analyst_tools": "analyst_tools", "finance": "finance", "END": END})
g.add_edge("analyst_tools", "analyst")

g.add_conditional_edges("finance", route_from_finance,
                        {"finance_tools": "finance_tools", "analyst": "analyst", "END": END})
g.add_edge("finance_tools", "finance")

memory = MemorySaver()
app = g.compile(checkpointer=memory)

# -------- Demo run --------
if __name__ == "__main__":
    user_msg = (
        "Investigate margin anomalies for the last 30 days. "
        "Escalate if total_loss exceeds 500."
    )
    out = app.invoke({"messages": [("user", user_msg)]},
                     config={"configurable": {"thread_id": "margin-demo-1"}})
    print(out["messages"][-1].content)

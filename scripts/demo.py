"""Run one live agent turn after following the README setup steps."""
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from langchain_core.messages import HumanMessage
from app import create_app
from app.models import Customer
from app.services.conversation_service import get_or_create_web_conversation
from agent.graph import build_graph

app = create_app()
with app.app_context():
    customer = Customer.query.first()
    thread_id = f"cli-demo:{uuid4()}"
    conversation = get_or_create_web_conversation(thread_id, customer.id if customer else None)
    message = " ".join(sys.argv[1:]) or "What is the Cairo delivery fee?"
    result = build_graph().invoke({"messages": [HumanMessage(content=message)], "conversation_id": conversation.id, "customer_id": conversation.customer_id}, config={"configurable": {"thread_id": thread_id}})
    print(result["response"])

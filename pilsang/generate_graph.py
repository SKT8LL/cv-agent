from test import app

try:
    print(app.get_graph().draw_mermaid())
except Exception as e:
    print(f"Error drawing graph: {e}")

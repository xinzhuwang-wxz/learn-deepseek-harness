"""Stage 1: an offline request -> tool -> observation loop. No API or shell."""
import json


class ScriptedModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def respond(self, messages):
        self.requests.append(json.loads(json.dumps(messages)))
        return next(self.responses, {"text": "script exhausted"})


def run(responses=None, max_steps=4, model=None):
    model = model or ScriptedModel(responses if responses is not None else [
        {"calls": [{"id": "c1", "name": "double", "args": {"value": 21}}]},
        {"text": "42"},
    ])
    messages = [{"role": "user", "content": "Double 21"}]
    tools = {"double": lambda args: args["value"] * 2}
    for _ in range(max_steps):
        response = model.respond(messages)
        messages.append({"role": "assistant", "content": response})
        calls = response.get("calls", [])
        if not calls:
            return messages
        for call in calls:
            try:
                value = tools[call["name"]](call["args"])
                result = {"ok": True, "value": value}
            except (KeyError, TypeError, ValueError) as exc:
                result = {"ok": False, "error": type(exc).__name__}
            messages.append({"role": "tool", "call_id": call["id"], "content": result})
    raise RuntimeError("teaching step budget exhausted")


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))

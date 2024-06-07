import json


def build_sse_data(message: str, id: str = ""):
    event_name = "chat_response"
    data = {"message": message, "id": id}
    sse_data = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
    return sse_data

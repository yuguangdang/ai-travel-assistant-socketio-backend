import json
import os
from flask import Flask, session
from flask_socketio import SocketIO
from dotenv import load_dotenv
from openai import OpenAI
from typing_extensions import override
from openai import AssistantEventHandler

from utils import get_itinerary

assistant_id = os.getenv("assistant_id")

client = OpenAI()

# Global variable to store the thread
global_thread = None

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text) -> None:
        print(f"********{text}********")
        print(f"\nassistant > ", end="", flush=True)
        # socketio.emit('chat message chunk', {'data': text})

    @override
    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)
        socketio.emit("chat message chunk", {"data": delta.value})

    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == "code_interpreter":
            if delta.code_interpreter.input:
                socketio.emit(
                    "chat message chunk", {"data": delta.code_interpreter.input}
                )
            if delta.code_interpreter.outputs:
                output_logs = "\n".join(
                    [
                        output.logs
                        for output in delta.code_interpreter.outputs
                        if output.type == "logs"
                    ]
                )
                socketio.emit("chat message chunk", {"data": output_logs})

    @override
    def on_event(self, event):
        # Retrieve events that are denoted with 'requires_action'
        # since these will have our tool_calls
        if event.event == "thread.run.requires_action":
            run_id = event.data.id  # Retrieve the run ID from the event data
            self.handle_requires_action(event.data, run_id)

    def handle_requires_action(self, data, run_id):
        tool_outputs = []

        for tool in data.required_action.submit_tool_outputs.tool_calls:
            if tool.function.name == "get_itinerary":
                pnr = json.loads(tool.function.arguments)["PNR"]
                itinerary = get_itinerary(pnr)
                tool_outputs.append({"tool_call_id": tool.id, "output": itinerary})
            elif tool.function.name == "cancel_flights":
                tool_outputs.append(
                    {"tool_call_id": tool.id, "output": "Flight cancelled successfully"}
                )
            elif tool.function.name == "change_flight":
                tool_outputs.append(
                    {"tool_call_id": tool.id, "output": "Flight changed successfully"}
                )

        # Submit all tool_outputs at the same time
        self.submit_tool_outputs(tool_outputs, run_id)

    def submit_tool_outputs(self, tool_outputs, run_id):
        # Use the submit_tool_outputs_stream helper
        with client.beta.threads.runs.submit_tool_outputs_stream(
            thread_id=self.current_run.thread_id,
            run_id=self.current_run.id,
            tool_outputs=tool_outputs,
            event_handler=EventHandler(),
        ) as stream:
            for text in stream.text_deltas:
                print(text, end="", flush=True)
            print()


@app.route("/")
def index():
    return "Chatbot Server is running"


@socketio.on("page_loaded")
def handle_message(data):    
    print("Page has been refreshed or loaded")
    if 'thread_id' not in session:
        thread = client.beta.threads.create()
        print("New thread has been created.")
        session['thread_id'] = thread.id
        print(f"New thread ({thread.id}) has been created for a new session.")
        add_message_to_thread(thread.id, "Hello")


@socketio.on("chat message")
def handle_message(message):    
    if 'thread_id' in session:
        thread_id = session['thread_id']
        print(f"Received message: {message}, using thread {thread_id}")
        add_message_to_thread(thread_id, message)


def add_message_to_thread(thread_id, message):
    print("")
    print("client >", message)
    message = client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=message
    )
    with client.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        event_handler=EventHandler(),
    ) as stream:
        stream.until_done()


if __name__ == "__main__":
    socketio.run(app, debug=True)

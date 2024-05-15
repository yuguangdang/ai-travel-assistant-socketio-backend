import json
import os
from flask import Flask, session, request
from flask_socketio import SocketIO
from dotenv import load_dotenv
from openai import AzureOpenAI
from typing_extensions import override
from openai import AssistantEventHandler

from functions import flight_schedule, get_itinerary, getLiveBookings, visa_check

assistant_id = os.getenv("ASSISTANT_ID")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-15-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

# Global variable to store the thread
global_thread = None

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


class EventHandler(AssistantEventHandler):
    def __init__(self, sid):
        super().__init__()
        self.sid = sid

    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)
        socketio.emit("chat message chunk", {"data": delta.value}, room=self.sid)

    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == "code_interpreter":
            if delta.code_interpreter.input:
                socketio.emit(
                    "chat message chunk",
                    {"data": delta.code_interpreter.input},
                    room=self.sid,
                )
            if delta.code_interpreter.outputs:
                output_logs = "\n".join(
                    [
                        output.logs
                        for output in delta.code_interpreter.outputs
                        if output.type == "logs"
                    ]
                )
                socketio.emit(
                    "chat message chunk", {"data": output_logs}, room=self.sid
                )

    @override
    def on_event(self, event):
        if event.event == "thread.run.requires_action":
            run_id = event.data.id  # Retrieve the run ID from the event data
            self.handle_requires_action(event.data, run_id)

    def handle_requires_action(self, data, run_id):
        tool_outputs = []
        for tool in data.required_action.submit_tool_outputs.tool_calls:
            if tool.function.name == "get_itinerary":
                arguments = json.loads(tool.function.arguments)
                print(f"{tool.function.name} arguments: {arguments}")
                pnr = arguments["PNR"]
                itinerary = get_itinerary(pnr)
                tool_outputs.append({"tool_call_id": tool.id, "output": itinerary})
            elif tool.function.name == "flight_schedule":
                arguments = json.loads(tool.function.arguments)
                print(f"{tool.function.name} arguments: {arguments}")
                departure_airport = arguments["departure_airport"]
                arrival_airport = arguments["arrival_airport"]
                year = arguments["year"]
                month = arguments["month"]
                day = arguments["day"]
                solution = flight_schedule(
                    departure_airport, arrival_airport, year, month, day
                )
                print(solution)
                tool_outputs.append(
                    {"tool_call_id": tool.id, "output": json.dumps(solution)}
                )
            elif tool.function.name == "visa_check":
                arguments = json.loads(tool.function.arguments)
                print(f"{tool.function.name} arguments: {arguments}")
                passportCountry = arguments.get("passportCountry")
                departureDate = arguments.get("departureDate")
                arrivalDate = arguments.get("arrivalDate")
                departureAirport = arguments.get("departureAirport")
                arrivalAirport = arguments.get("arrivalAirport")
                transitCities = arguments.get("transitCities", [])
                travelPurpose = arguments.get("travelPurpose")
                result = visa_check(
                    passportCountry,
                    departureDate,
                    arrivalDate,
                    departureAirport,
                    arrivalAirport,
                    transitCities,
                    travelPurpose,
                )
                print(result)
                tool_outputs.append(
                    {"tool_call_id": tool.id, "output": json.dumps(result)}
                )
            elif tool.function.name == "getLiveBookings":
                arguments = json.loads(tool.function.arguments)
                print(f"{tool.function.name} arguments: {arguments}")
                role = arguments["role"]
                email = arguments["email"]
                debtorId = arguments["debtorId"]
                bookings = getLiveBookings(role, email, debtorId)
                print(bookings)
                tool_outputs.append(
                    {"tool_call_id": tool.id, "output": json.dumps(bookings)}
                )

        self.submit_tool_outputs(tool_outputs, run_id)

    def submit_tool_outputs(self, tool_outputs, run_id):
        with client.beta.threads.runs.submit_tool_outputs_stream(
            thread_id=self.current_run.thread_id,
            run_id=self.current_run.id,
            tool_outputs=tool_outputs,
        ) as stream:
            for text in stream.text_deltas:
                print(text, end="", flush=True)
                socketio.emit("chat message chunk", {"data": text}, room=self.sid)
            print()


@app.route("/")
def index():
    return "Chatbot Server is running"


@socketio.on("session_start")
def handle_session_start(data):
    print("Websokcet connection established. Session started.")
    session["metadata"] = data
    print("Session metadata saved:", session)
    if "thread_id" not in session:
        thread = client.beta.threads.create()
        print("New thread has been created.")
        session["thread_id"] = thread.id
        print(f"New thread ({thread.id}) has been created for a new session.")
        greeting_prompt = (
            f"Hello, please remember my metadata throughout our conversation: {data}"
        )
        add_message_to_thread(thread.id, greeting_prompt, request.sid)


@socketio.on("chat message")
def handle_message(message):
    if "thread_id" in session:
        thread_id = session["thread_id"]
        print(f"Received message: {message}, using thread {thread_id}")
        add_message_to_thread(thread_id, message, request.sid)


def add_message_to_thread(thread_id, message, sid):
    print(f"\nclient >", message)
    message = client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=message
    )
    with client.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        event_handler=EventHandler(sid),
    ) as stream:
        stream.until_done()


if __name__ == "__main__":
    socketio.run(app, debug=True)

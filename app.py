import os
from flask import Flask, session, request
from flask_jwt_extended import JWTManager, decode_token
from flask_socketio import SocketIO, disconnect
from flask_session import Session
from dotenv import load_dotenv
from openai import AzureOpenAI
import redis

from event_handlers import add_message_to_thread

# Load environment variables from .env file
load_dotenv()

# Initialize Redis
try:
    redis_client = redis.StrictRedis(
        host=os.getenv("REDIS_HOST"),
        port=6379,
        password=os.getenv("REDIS_PASSWORD"),
        ssl=False,  # Ensure SSL is disabled
    )
    redis_client.ping()
    print("Connected to Redis server.")
except redis.ConnectionError as e:
    print(f"Could not connect to Redis server: {e}")
    exit(1)


# Initialize Azure OpenAI client with environment variables
assistant_id = os.getenv("ASSISTANT_ID")
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-15-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

# Initialize Flask app and Flask-SocketIO
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "secret_key_provided_by_portal"
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_REDIS"] = redis_client
Session(app)
jwt = JWTManager(app)
socketio = SocketIO(app, cors_allowed_origins="*")


# Define a simple route to check if the server is running
@app.route("/")
def index():
    return "Chatbot Server is running"


# Event handler for 'session_start' event
@socketio.on("connect")
def handle_session_start():
    try:
        # Log connection establishment
        print("WebSocket connection established. Session started.")
        token = request.args.get("token")
        if token:
            # Save the session metadata
            decoded_token = decode_token(token)
            session["metadata"] = decoded_token
            print("Session metadata saved:", session)

            # Check if a thread ID is already in the session, if not, create a new thread
            if "thread_id" not in session:
                thread = client.beta.threads.create()
                print("New thread has been created.")
                session["thread_id"] = thread.id
                print(f"New thread ({thread.id}) has been created for a new session.")

                # Create a greeting prompt including the metadata
                greeting_prompt = f"Hello, please remember my metadata throughout our conversation: {session['metadata']}"

                # Add the greeting message to the thread
                add_message_to_thread(
                    thread.id, greeting_prompt, request.sid, client, socketio
                )
        else:
            print("No token provided.")
            disconnect()
    except Exception as e:
        print("JWT verification failed:", e)
        disconnect()


# Event handler for 'chat message' event
@socketio.on("chat message")
def handle_message(message):
    # Check if a thread ID is in the session
    if "thread_id" in session:
        thread_id = session["thread_id"]
        print(f"Received message: {message}, using thread {thread_id}")

        # Add the received message to the thread
        add_message_to_thread(thread_id, message, request.sid, client, socketio)


# Run the Flask-SocketIO server
if __name__ == "__main__":
    socketio.run(app, debug=True)

import json
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
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = False
app.config["SESSION_REDIS"] = redis_client
Session(app)
jwt = JWTManager(app)
socketio = SocketIO(app, manage_session=True, cors_allowed_origins="*")


# Helper functions to save and retrieve session data from Redis
def save_session_to_redis(token, data):
    # Convert the data dictionary to a JSON string
    redis_client.set(f"session:{token}", json.dumps(data))


def get_session_from_redis(token):
    # Retrieve the data from Redis and convert it back to a dictionary
    data = redis_client.get(f"session:{token}")
    if data:
        return json.loads(data.decode("utf-8"))  # Decode bytes to string and parse JSON
    return None


# Define a simple route to check if the server is running
@app.route("/")
def index():
    return "Chatbot Server is running"


# Event handler for 'session_start' event
@socketio.on("connect")
def handle_session_start():
    try:
        # Log connection establishment
        token = request.args.get("token")
        if token:
            # Check if session data exists in Redis
            session_data = get_session_from_redis(token)
            if not session_data:
                # If no session data, create new session and thread
                metadata = decode_token(token)
                session_data = {"metadata": metadata, "sid": request.sid}

                thread = client.beta.threads.create()
                session_data["thread_id"] = thread.id
                save_session_to_redis(token, session_data)
                print(f"New session created: {session_data}")

                # Create a greeting prompt including the metadata
                greeting_prompt = f"Hello, please remember my metadata throughout our conversation: {metadata}"

                # Add the greeting message to the thread
                add_message_to_thread(
                    thread.id, greeting_prompt, request.sid, client, socketio
                )
            else:
                # Check if the session already has a sid
                if session_data.get("sid"):
                    print(
                        "A session is already active, disconnecting this new connection."
                    )
                    disconnect()
                else:
                    # It has session but sid is None, hence, need to save the new sid
                    session_data["sid"] = request.sid
                    save_session_to_redis(token, session_data)
                    thread_id = session_data["thread_id"]
                    reconnect_prompt = f"Hello again, I'm back."

                    # Add the greeting message to the thread
                    add_message_to_thread(
                        thread_id, reconnect_prompt, request.sid, client, socketio
                    )
                    print("Session data retrieved from Redis:", session_data)
        else:
            print("No token provided.")
            disconnect()
    except Exception as e:
        print("JWT verification failed:", e)
        disconnect()


# Event handler for 'disconnect' event
@socketio.on("disconnect")
def handle_disconnect():
    try:
        token = request.args.get("token")
        if token:
            session_data = get_session_from_redis(token)
            if session_data and session_data.get("sid") == request.sid:
                # Remove sid from session data on disconnect
                session_data["sid"] = None
                save_session_to_redis(token, session_data)
                print(f"Session sid cleared for token: {token}")
    except Exception as e:
        print(f"Error during disconnect: {e}")


# Event handler for 'chat message' event
@socketio.on("chat message")
def handle_message(data):
    token = data.get("token")
    message = data.get("message")
    if token:
        # Retrieve session data from Redis
        session_data = get_session_from_redis(token)
        if session_data:
            print("Session data in 'chat message' handler:", session_data)

            if "thread_id" in session_data:
                thread_id = session_data["thread_id"]
                print(f"Received message: {message}, using thread {thread_id}")

                # Add the received message to the thread
                add_message_to_thread(thread_id, message, request.sid, client, socketio)
            else:
                print("No thread ID found in the session.")
        else:
            print("No session data found.")
    else:
        print("No token provided.")


# Run the Flask-SocketIO server
if __name__ == "__main__":
    socketio.run(app, debug=True)

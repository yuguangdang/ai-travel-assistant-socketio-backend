## Overview

This is the WebSocket backend of the AI travel assistant that leverages Flask, Flask-SocketIO, and Azure OpenAI to provide interactive chat services. The server is designed to handle chat sessions, manage user data with Redis, and integrate various tools and APIs to enhance the chat experience.

## Architecture
<img width="882" height="662" alt="intro-m" src="https://github.com/yuguangdang/ai-travel-assistant-frontend/assets/55920971/32ec8ed4-f30a-43d7-8d72-cbde5081475d">


## Features

- **Flask Web Server**: Provides the main application framework.
- **Flask-SocketIO**: Enables real-time bidirectional communication between the server and clients.
- **JWT Authentication**: Secures communication with JSON Web Tokens.
- **Redis**: Manages session data for scalability and reliability.
- **Azure OpenAI**: Powers the chatbot with advanced AI capabilities.
- **Event Handlers**: Custom event handling for different types of chat messages and actions.
- **API Integrations**: Includes functions for itinerary retrieval, flight schedules, visa checks, live bookings, and more.

### A demo recording
https://www.youtube.com/watch?v=jOkmDwpewiE&ab_channel=StaryAI

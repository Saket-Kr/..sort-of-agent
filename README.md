# Reasoning Engine Pro

Production-grade agentic workflow planning system with native OpenAI function calling, Pydantic schemas, and SOLID architecture.

## Features

- **Native OpenAI Function Calling**: Direct integration with LLM function calling APIs
- **Pydantic Schemas**: Type-safe data validation throughout
- **Strategy/Factory Patterns**: Swappable LLM providers and services
- **FastAPI for REST & WebSocket**: Unified framework for all API endpoints
- **Redis Storage**: Persistent conversation state with TTL support
- **Langfuse Integration**: Built-in observability and tracing
- **Built-in Web Client**: Production-ready chat interface served at `/app`

## Quick Start

### Prerequisites

- Python 3.11+
- Redis (optional, for persistence)
- Docker & Docker Compose (for containerized deployment)

### Local Development

1. **Clone and setup**:
   ```bash
   cd reasoning-engine-pro
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -e ".[dev]"
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run the server**:
   ```bash
   python -m reasoning_engine_pro.main
   ```

4. **Open the web client**:
   Navigate to `http://localhost:8765/app` in your browser.

### Docker Deployment

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f reasoning-engine

# Stop services
docker-compose down
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider type (`vllm` or `openai`) | `vllm` |
| `LLM_BASE_URL` | LLM API base URL | `http://localhost:8000/v1` |
| `LLM_API_KEY` | LLM API key | - |
| `LLM_MODEL_NAME` | Model name to use | - |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `WS_PORT` | WebSocket server port | `8765` |
| `MAX_CONCURRENT_CONNECTIONS` | Max WebSocket connections | `50` |

## API Reference

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server info |
| `/health` | GET | Health check |
| `/info` | GET | Server stats & uptime |
| `/app` | GET | Web client interface |
| `/wilfred_v4/planner-dashboard/input_analysis` | POST | Input analysis |

### WebSocket Events

#### Client → Server

| Event | Description |
|-------|-------------|
| `start_chat` | Start new conversation |
| `provide_clarification` | User response to clarification |
| `end_chat` | End conversation |
| `ping` | Keep-alive |
| `input_analysis` | Referencing analysis request |

#### Server → Client

| Event | Description |
|-------|-------------|
| `processing_started` | Message received |
| `stream_response` | Streaming LLM response |
| `clarification_requested` | Agent needs user input |
| `clarification_received` | Acknowledge clarification |
| `web_search_started` | Search started |
| `web_search_results` | Search results |
| `task_block_search_started` | Block search started |
| `task_block_search_results` | Block search results |
| `opkey_workflow_json` | Final workflow output |
| `validator_progress_update` | Validation progress |
| `error` | Error notification |

### WebSocket Example

```javascript
const ws = new WebSocket('ws://localhost:8765/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    event: 'start_chat',
    payload: {
      chat_id: 'unique-id',
      message: 'Create a workflow to export HCM configuration'
    }
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.event, 'Payload:', data.payload);
};
```

## Web Client

The built-in web client is available at `http://localhost:8765/app` and provides:

- **Real-time Chat Interface**: Send messages and receive streaming responses
- **Clarification Handling**: Modal dialogs for answering clarification questions
- **Workflow Visualization**: View and download generated workflows
- **Search Results**: Side panel showing web and task block search results
- **Connection Management**: Auto-reconnection with visual status indicator
- **Multiple Conversations**: Sidebar for managing multiple chat sessions

### Web Client Architecture

```
web_client/
├── index.html           # Main HTML page
├── css/
│   └── styles.css       # All styles (CSS variables, responsive)
└── js/
    ├── websocket-client.js   # WebSocket connection management
    ├── chat-manager.js       # Conversation state management
    ├── ui-controller.js      # DOM manipulation and rendering
    └── app.js                # Main application logic
```

The web client uses vanilla JavaScript with a modular architecture (no build step required).

## Architecture

```
reasoning-engine-pro/
├── src/reasoning_engine_pro/
│   ├── core/           # Domain layer (schemas, interfaces)
│   ├── llm/            # LLM abstraction layer
│   ├── tools/          # Tool system
│   ├── services/       # External service integrations
│   ├── agents/         # Agent orchestration
│   ├── api/            # FastAPI REST & WebSocket
│   └── observability/  # Logging & tracing
├── web_client/         # Built-in web interface
└── tests/              # Test suite
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=reasoning_engine_pro

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

## License

MIT
# ..sort-of-agent

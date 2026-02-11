# ScholarBot Architecture

## System Overview

ScholarBot is a conversational AI agent built with LangGraph and LangChain that enables natural language search of the CSUSB library system.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit UI (app.py)                   │
│                  User Interface & Session Management         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ User Input
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              ScholarAgent (LangGraph)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Agent Node                                         │   │
│  │  - System Prompt                                    │   │
│  │  - OpenAI GPT-4                                     │   │
│  │  - Parameter Extraction                             │   │
│  │  - Tool Selection                                   │   │
│  └──────────────┬──────────────────────────────────────┘   │
│                 │                                           │
│                 │ Tool Calls                                │
│                 ▼                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Tool Node                                          │   │
│  │  - get_library_resources                            │   │
│  └──────────────┬──────────────────────────────────────┘   │
│                 │                                           │
│  ┌──────────────▼──────────────────────────────────────┐   │
│  │  Memory (InMemorySaver)                             │   │
│  │  - Conversation History                             │   │
│  │  - Thread-based State                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ API Calls
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            CSUSBLibraryClient                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  - Query Formatting                                 │   │
│  │  - Parameter Validation                             │   │
│  │  - HTTP Request Management                          │   │
│  │  - Response Parsing                                 │   │
│  └──────────────┬──────────────────────────────────────┘   │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ HTTPS
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              CSUSB Library Primo API                        │
│              (External Service)                             │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Streamlit UI Layer (`app.py`)

**Responsibilities:**
- User interface rendering
- Session state management
- Message history tracking
- User input collection
- Response display

**Key Features:**
- Real-time chat interface
- Conversation history
- Settings sidebar
- Clear conversation button
- Error handling and display

### 2. Agent Layer (`agents/scholar_agent.py`)

**Components:**

#### ScholarAgent Class
- **LangGraph Workflow**: Defines conversation flow
- **State Management**: Tracks conversation state across turns
- **Tool Orchestration**: Decides when to call tools
- **Response Generation**: Produces natural language responses

**Workflow:**
```
User Input → Agent Node → [Tool Call?]
                ↓              ↓
            [No Tool]       Tool Node
                ↓              ↓
            Response    → Agent Node
                           ↓
                       Response
```

**Key Methods:**
- `chat()`: Synchronous chat method
- `stream_chat()`: Streaming response method
- `_call_model()`: LLM invocation
- `_should_continue()`: Decision logic for tool calls

### 3. Tools Layer (`core/tools/library_tools.py`)

**get_library_resources Tool:**

**Input Schema:**
- `query`: Search keywords
- `resource_type`: Optional filter (article, book, journal, thesis)
- `date_from`: Optional start year
- `date_to`: Optional end year
- `limit`: Result count (1-50)

**Output:**
- Formatted string with search results
- Includes: titles, authors, years, types, URLs

**Features:**
- Structured input validation via Pydantic
- Error handling and fallback messages
- Result formatting for readability

### 4. Client Layer (`core/clients/csusb_library_client.py`)

**CSUSBLibraryClient Class:**

**Responsibilities:**
- API request construction
- Query parameter formatting
- HTTP session management
- Response parsing
- Error handling

**Features:**
- Retry logic with exponential backoff
- Request timeout management
- Date normalization
- Resource type mapping
- Comprehensive logging

### 5. Utilities (`core/utils/`)

**logging_utils.py:**
- Centralized logging configuration
- Consistent log formatting
- Environment-based log levels

**dates.py:**
- Date format normalization (YYYY → YYYYMMDD)
- Boundary calculation (start of year, end of year)
- Future date clamping

## Data Flow

### Typical Search Query Flow

1. **User Input**: "Find recent articles on machine learning from 2023"

2. **Streamlit UI**:
   - Captures input
   - Adds to session messages
   - Calls agent.chat()

3. **Agent (LLM Processing)**:
   - Receives message with system prompt
   - Extracts parameters:
     - query: "machine learning"
     - resource_type: "article"
     - date_from: 2023
     - date_to: 2023
   - Decides to call get_library_resources tool

4. **Tool Execution**:
   - Validates parameters
   - Calls CSUSBLibraryClient.search()

5. **Library Client**:
   - Formats Primo API query
   - Adds filters (resource type, dates)
   - Makes HTTP request
   - Parses JSON response

6. **Tool Result**:
   - Formats results into readable text
   - Returns to agent

7. **Agent (Response Generation)**:
   - Receives tool results
   - Generates natural language response
   - Returns to Streamlit

8. **UI Display**:
   - Shows response to user
   - Saves to message history

## State Management

### Conversation State

**Thread-based Memory:**
```python
{
    "thread_id": "unique-uuid",
    "messages": [
        SystemMessage(...),
        HumanMessage(...),
        AIMessage(...),
        HumanMessage(...),
        AIMessage(...)
    ]
}
```

**Context Retention:**
- Each thread maintains its own conversation history
- Messages accumulate across turns
- Agent can reference previous exchanges
- Enables natural follow-up questions

### Session State (Streamlit)

```python
{
    "messages": [],      # Chat history for display
    "thread_id": "...",  # Current conversation thread
    "agent": ScholarAgent()  # Initialized agent instance
}
```

## Design Patterns

### 1. Dependency Inversion
- `ILibraryClient` interface
- Allows easy mocking and testing
- Enables alternative implementations

### 2. Factory Pattern
- `create_scholar_agent()` function
- Encapsulates agent initialization
- Simplifies configuration

### 3. Tool Pattern (LangChain)
- Declarative tool definition with `@tool` decorator
- Automatic schema generation from Pydantic models
- Type-safe parameter passing

### 4. State Management (LangGraph)
- Explicit state definition with TypedDict
- Immutable state updates
- Checkpointing for conversation persistence

## Error Handling

### Layers of Error Handling

1. **Tool Layer**:
   - Catches API errors
   - Returns error messages to agent
   - Logs detailed errors

2. **Agent Layer**:
   - Wraps tool calls in try-catch
   - Generates friendly error messages
   - Maintains conversation flow

3. **UI Layer**:
   - Displays error messages to user
   - Logs errors for debugging
   - Prevents app crashes

### Error Recovery Strategies

- **No Results**: Suggest alternative search terms
- **API Timeout**: Retry with backoff
- **Invalid Parameters**: Request clarification
- **Network Error**: Inform user and suggest retry

## Performance Optimizations

### Response Time

1. **Efficient API Calls**:
   - Connection pooling (requests.Session)
   - Timeout configuration
   - Retry logic

2. **Model Selection**:
   - GPT-4 for quality (slower)
   - GPT-3.5-turbo for speed (faster)
   - Configurable via environment

3. **Result Limiting**:
   - Default 10 results
   - Maximum 50 results
   - Reduces processing time

### Memory Management

1. **Stateful Conversations**:
   - Thread-based isolation
   - Automatic garbage collection
   - No persistent storage (in-memory only)

2. **Session State**:
   - Minimal state storage
   - Agent singleton per session
   - Message history truncation (future enhancement)

## Security Considerations

### API Key Management
- Environment variable storage
- Never committed to version control
- Validated on startup

### Input Validation
- Pydantic schema validation
- Parameter sanitization
- SQL injection prevention (parameterized queries in Primo API)

### Rate Limiting
- Retry logic to handle 429 responses
- Timeout configuration
- Graceful degradation

## Testing Strategy

### Unit Tests (Future)
- Tool parameter validation
- Date normalization logic
- Response formatting

### Integration Tests
- `test_agent.py` for manual testing
- Interactive mode for exploration
- Automated test scenarios

### Manual Testing
- Streamlit UI testing
- Conversation flow validation
- Edge case exploration

## Extensibility

### Adding New Tools

1. Define tool function in `core/tools/`
2. Add to `LIBRARY_TOOLS` list
3. Update system prompt if needed
4. Agent automatically discovers new tools

### Alternative Library Clients

1. Implement `ILibraryClient` interface
2. Replace `CSUSBLibraryClient` in tools
3. No changes to agent required

### Custom Models

1. Change `OPENAI_MODEL` in `.env`
2. Or pass `model_name` to `create_scholar_agent()`
3. Works with any OpenAI-compatible model

## Future Enhancements

1. **Persistent Storage**: Save conversation history to database
2. **Advanced Filters**: Subject, language, availability filters
3. **Citation Management**: Export citations in various formats
4. **Multi-modal**: Accept uploaded PDFs for context
5. **Recommendation Engine**: Suggest related resources
6. **User Profiles**: Save preferences and search history
7. **Analytics**: Track popular queries and resources
8. **Feedback Loop**: Learn from user interactions

## Conclusion

ScholarBot demonstrates a production-ready architecture for conversational AI applications with:
- Clean separation of concerns
- Robust error handling
- Stateful conversations
- Extensible design
- User-friendly interface

The architecture supports both current functionality and future enhancements while maintaining code quality and maintainability.

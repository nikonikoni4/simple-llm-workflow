# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a data-driven LLM Agent execution framework with a visual debugging interface. It provides:
- **Multi-threaded execution engine**: Supports parallel execution paths with isolated contexts
- **Visual flow designer**: PyQt-based UI for designing execution plans with nodes and connections
- **Step-by-step debugging**: Single-step execution with detailed context inspection
- **REST API backend**: FastAPI server for executor management and control

## Key Architecture Components

### Core Execution Engine

The execution system has two versions:

1. **Synchronous Executor** (`data_driving_agent_v2/executor.py`):
   - Direct execution of plans
   - Use for simple, one-shot execution
   - Initializes with: `Executor(plan, user_message, tools_map, tools_limit)`

2. **Asynchronous Executor** (`data_driving_agent_v2/async_executor.py`):
   - Async version for API integration
   - Provides state tracking and context collection
   - Supports single-step execution via `execute_step()`
   - Used by the FastAPI backend

### Node Types

The system supports three node types (defined in `data_driving_agent_v2/data_driving_schemas.py`):

- **llm-first**: LLM executes first, optionally calling tools. Use when reasoning should precede action.
- **tool-first**: Tool executes first, then LLM analyzes results. Requires `initial_tool_name` and `initial_tool_args`.
- **planning**: Generates sub-plans recursively (not yet implemented).

### Thread Model

- **Context isolation**: Each thread has its own message history
- **Thread creation**: New threads are created only when a node with a new `thread_id` is encountered
- **data_in**: Controls what context from parent threads is injected into child threads (only applies on thread creation)
- **data_out**: Merges child thread results back to parent thread when `data_out=True`

### Tool Configuration

Use the `ToolConfig` class (`data_driving_agent_v2/tool_config.py`) to manage tools:

```python
config = ToolConfig(api_key="your-api-key")
config.register_tool("tool_name", tool_function, limit=5)
tools_map = config.get_tools_map()
tools_limit = config.get_tools_limit()
```

## Common Development Commands

### Starting the Backend API

```bash
cd front
uvicorn backend_api:app --reload --port 8001
```

The API will be available at `http://localhost:8001` with interactive docs at `http://localhost:8001/docs`.

### Testing

Run the test suite:
```bash
cd test
python test_integration.py
```

Or use the provided batch script (Windows):
```bash
cd test
run_test.bat
```

### Running with a Custom Plan

See `data_driving_agent_v2/function_example.py` for an example of creating and executing a plan.

## Frontend Architecture

The PyQt frontend consists of:

- **Node Graph View** (`front/debugger_ui.py`): Visual flow designer with drag-and-drop node editing
- **Execution Panel** (`front/execution_panel.py`): Control panel for running and debugging plans
- **API Client** (`front/api_client.py`): Async HTTP client for backend communication

## Data Flow

1. **Plan Creation**: Use the visual UI or create `ExecutionPlan` objects programmatically
2. **Executor Initialization**: Backend creates an `AsyncExecutor` with the plan and tools
3. **Execution**: Execute the entire plan at once or step-by-step for debugging
4. **Context Inspection**: Retrieve detailed context for each node including LLM inputs/outputs

## Important Implementation Details

### Thread Initialization (Critical)

Thread initialization with `data_in` **only happens once** when the thread is first created. Only the first node that creates a thread will have its `data_in` configuration applied. Subsequent nodes in the same thread are ignored.

### Tool Execution

Tools are LangChain tools decorated with `@tool`. They must be registered with the executor before use. Tool usage limits are enforced per execution.

### Message Serialization

The async executor serializes LangChain messages for frontend consumption. See `_serialize_messages()` in `async_executor.py:332`.

### State Management

The async executor maintains:
- `node_states`: Execution status (PENDING/RUNNING/COMPLETED/FAILED) for each node
- `node_contexts`: Detailed execution context for each node (for UI display)
- `_current_node_index`: Current position for step-by-step execution

## Backend API Endpoints

- `POST /api/executor/init` - Initialize a new executor
- `POST /api/executor/{id}/run` - Run entire plan in background
- `POST /api/executor/{id}/run-sync` - Run synchronously and wait for completion
- `POST /api/executor/{id}/step` - Execute single step
- `GET /api/executor/{id}/status` - Get execution status and progress
- `GET /api/executor/{id}/nodes/{node_id}/context` - Get node context details
- `DELETE /api/executor/{id}` - Terminate executor
- `GET /api/tools` - List registered tools

## Environment Setup

Required dependencies:
```bash
pip install fastapi uvicorn aiohttp langchain-core langchain-openai pydantic
```

Set API key:
```powershell
$env:OPENAI_API_KEY="your-api-key"  # For OpenAI
$env:DASHSCOPE_API_KEY="your-api-key"  # For Alibaba DashScope (通义千问)
```

## File Organization

```
data_driving_agent_v2/
├── executor.py          # Synchronous executor
├── async_executor.py    # Asynchronous executor with state tracking
├── data_driving_schemas.py  # Pydantic models for plans and nodes
├── tool_config.py       # Tool and LLM configuration management
├── plan_generator.py    # LLM-based plan generation
└── function_example.py  # Example usage

front/
├── backend_api.py       # FastAPI server
├── api_client.py        # Async HTTP client
├── debugger_ui.py       # PyQt visual flow designer
└── execution_panel.py   # Execution control UI

test/
├── test_fuction/        # Example tools (get_daily_stats)
└── patterns/            # Test plan templates
```

## Development Guidelines

- **Async vs Sync**: Use `AsyncExecutor` for API integration and debugging features. Use `Executor` for simple script execution.
- **Thread Management**: Always set `parent_thread_id` when creating child threads to enable proper `data_out` merging.
- **Tool Limits**: Set appropriate tool limits to prevent infinite loops in tool-calling nodes.
- **Error Handling**: The async executor captures errors in `node_states` but still raises exceptions. Handle appropriately in API responses.
- **Frontend Integration**: Use `ExecutorController` from `api_client.py` in PyQt components for async API communication.

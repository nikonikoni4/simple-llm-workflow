# 前后端 API 交互文档

本文档说明了 Simple LLM Workflow 中前端（Qt/Python Client）与后端（FastAPI Server）之间的交互机制。

## 1. 概述

前后端通过 HTTP RESTful API 进行通信。
- **后端**: 基于 FastAPI 构建，负责核心逻辑执行（`AsyncExecutor`）、状态管理和工具调用。
- **前端**: 基于 `aiohttp` (异步) 或 `requests` (同步，如有) 封装的 `ExecutorAPIClient`，负责发送指令和展示状态。
- **数据格式**: JSON。后端使用 Pydantic 模型定义 Schema，前端使用 Python Dataclasses 或字典映射。

## 2. 交互流程详解

以下是核心功能的调用流程和数据交换说明。

### 2.1. 服务检查与工具加载

在应用启动时，前端会检查后端健康状态并获取可用工具。

*   **健康检查**
    *   **Endpoint**: `GET /`
    *   **前端调用**: `client.health_check()`
    *   **数据**: 无请求体。返回 `{ "status": "running", ... }`。

*   **获取工具列表**
    *   **Endpoint**: `GET /api/tools`
    *   **前端调用**: `client.list_tools()`
    *   **后端处理**: 遍历 `executor_manager._tools_registry`。
    *   **数据**: 返回工具列表，包含名称、描述和参数 Schema。前端用于在 UI 上提示可用工具。

### 2.2. 执行器初始化 (Init)

用户在前端加载或编辑好执行计划（Execution Plan）后，点击“初始化”或“开始”时触发。

*   **Endpoint**: `POST /api/executor/init`
*   **前端调用**: `client.init_executor(plan, user_message, ...)`
*   **数据交换**:
    *   **Request (`InitExecutorRequest`)**:
        *   `plan`: 完整的执行计划结构即 `ExecutionPlan` (包含 nodes, edges 等)。
        *   `user_message`: 用户输入的初始任务描述。
        *   `default_tool_limit`: 工具调用次数限制。
        *   `llm_config`: 模型配置 (温度, API Key 等)。
    *   **Response (`InitExecutorResponse`)**:
        *   `executor_id`: **关键**，后续所有操作的唯一标识凭证。
        *   `status`: "initialized"
        *   `node_count`: 确认节点数量。

### 2.3. 执行控制 (Run / Step)

初始化后，通过 `executor_id` 控制执行流程。

#### 2.3.1. 完整运行 (后台异步)
*   **Endpoint**: `POST /api/executor/{executor_id}/run`
*   **前端调用**: `client.run_executor(executor_id)`
*   **交互逻辑**:
    1.  后端接收请求，创建一个 `BackgroundTasks` 任务来运行 `executor.execute()`。
    2.  后端**立即返回**，不等待执行完成。
    3.  前端通过轮询（Polling）状态接口来更新进度。
*   **Response (`ExecutionResultResponse`)**: 包含 `status: "running"`。

#### 2.3.2. 单步执行
*   **Endpoint**: `POST /api/executor/{executor_id}/step`
*   **前端调用**: `client.step_executor(executor_id, node_id=None)`
*   **交互逻辑**:
    1.  后端执行**下一个**待执行节点（或指定的 `node_id`）。
    2.  **等待**该节点执行完毕。
    3.  返回该节点的执行结果上下文。
*   **Response**:
    *   `node_context`: 完成节点的详细信息（LLM 输入输出、工具调用等）。
    *   `progress`: 当前进度信息。

### 2.4. 状态监控与数据获取

在自动运行过程中，前端通过定时器轮询后端获取最新状态。

#### 2.4.1. 获取状态
*   **Endpoint**: `GET /api/executor/{executor_id}/status`
*   **前端调用**: `client.get_executor_status(executor_id)`
*   **数据 (`ExecutorStatusResponse`)**:
    *   `overall_status`: "running", "completed", "failed" 等。
    *   `progress`: `{ "total": 10, "completed": 5, ... }`
    *   `node_states`: 所有节点的状态列表（waiting, running, completed, error）。前端据此刷新 DAG 图的颜色状态。

#### 2.4.2. 获取节点详情 (点击节点时)
*   **Endpoint**: `GET /api/executor/{executor_id}/nodes/{node_id}/context`
*   **前端调用**: `client.get_node_context(executor_id, node_id)`
*   **数据 (`NodeContextResponse`)**:
    *   `llm_input` / `llm_output`: 模型的完整对话记录。
    *   `tool_calls`: 该节点产生的工具调用详情。
    *   `thread_messages_...`: 执行前后的消息历史。
    *   前端使用这些数据在“属性面板”或“调试窗口”显示详细信息。

#### 2.4.3. 获取消息历史
*   **Endpoint**: `GET /api/executor/{executor_id}/messages`
*   **数据**: 返回特定线程 (`thread_id`) 或所有线程的聊天记录列表。

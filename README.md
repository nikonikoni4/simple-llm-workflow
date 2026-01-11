# Simple LLM Playground

一个基于 `llm-linear-executor` 的 Qt 可视化界面，旨在通过图形化操作快速生成、调试和验证 LLM Workflow。

<p align="center">图 ：simple-llm-playground界面</p>

![alt text](/asset/image.png)


## Simple LLM Playground 能做什么？


- **可视化编排**：通过直观的节点连接生成 Workflow，支持 LLM 节点与 Tool 节点的混合编排。
- **实时调试**：内置 Executor 引擎，可直接运行设计好的流程，实时查看每一步的输出结果。
- **自定义扩展**：
- **自定义工具**：支持通过简单的装饰器将 Python 函数注册为 Tool，通过在main.py中导入工具函数（基于langchain的@tool装饰器的工具函数，或在导入后增加@tool装饰器包装函数），快速接入本地数据或业务逻辑。

## Simple LLM Playground 有什么局限性？

当前只有两种节点llm-first和tool-first，缺少router节点，有些情况下只能多创建一条线程，来实现。（在后续更新中会思考解决这个问题）

## 快速开始

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置模型

```python
# main.py
api_key = "your_api_key" 
model = "gpt-4o"
llm_factory = create_llm_factory(model,api_key,chat_model=ChatOpenAI)
```

3. 配置工具

在main.py中导入工具函数（基于langchain的@tool装饰器的工具函数，或在导入后增加@tool装饰器包装函数），快速接入本地数据或业务逻辑。

```python
from simple_llm_playground.server.executor_manager import executor_manager
from your_path import ( tools )

executor_manager.register_tool("your_tool_name", your_tool)
```
4. 终端运行

```bash
.\run.bat
```

## 界面配置说明

### 1. 加载和保存 Plan
界面左上角包含两个核心功能：
- **Load JSON Plan**：加载本地的 `.json` 格式 Plan 文件。加载后，画布将自动渲染节点结构。
- **Save JSON Plan**：将当前的节点编排保存为 `.json` 文件。
> **提示**：所有的 Plan 结构及节点内容（包括 Prompt、工具配置等）均以标准的 JSON 格式保存。

### 2. Execute Control (执行控制)
位于左侧面板，用于控制工作流的生命周期：
- **Initialize**：初始化执行器状态。加载新 Plan 或修改配置后特别是需要重置上下文时使用。
- **Stop**：中断当前的执行任务。
- **Step**：单步执行。点击一次仅执行下一个待运行节点，便于逐步调试和观察中间状态。
- **Run All**：连续执行整个 Workflow，直到流程结束或出错。

### 3. User Message
- **User Message**：用户输入区域。此处输入的内容将作为初始的用户消息（User Prompt），并默认注入到 `main` 线程中，作为整个 Workflow 的起始上下文数据。
### 4. Node Context
位于左侧面板下方，用于展示**当前选中节点**（或最近执行节点）的运行时详情，是调试的核心区域：
- **Context Information**：显示当前节点输入的所有上下文消息（Message History）。这是执行 `data_in_slice` 切片操作后的最终输入数据。
- **LLM Input Prompt**：显示实际发送给 LLM 的完整 Prompt（包含 System Prompt 和 Context）。用于检查 Prompt 组装是否符合预期。
- **Node Output**：显示当前节点执行完成后的输出结果（LLM 的回复内容或工具的执行结果）。
### 5. Node Setting (节点配置)
在画布中选中任一节点后，通过底部的 `Node Properties` 面板进行详细配置。各配置项对应 `llm-linear-executor` 的 Schema 定义：

#### Node Setting (基础设置)
- **Name (`node_name`)**：节点名称，用于标识节点，需保持唯一。
- **Type (`node_type`)**：节点类型。
  - `llm-first`：先进行 LLM 思考，再根据需要调用工具。
  - `tool-first`：强制首先执行指定工具，再由 LLM 分析结果。
- **Branch (`thread_id`)**：当前节点运行所在的线程 ID。
- **Src Thread (`data_in_thread`)**：输入数据的来源线程 ID（默认为 `main`）。
- **Slice (`data_in_slice`)**：输入消息的切片范围。例如 `0,2` 表示取前两条，`-1,` 表示取最后一条。
- **Output Data to Parent (`data_out`)**：勾选后，该节点的执行结果将被输出。
- **Out Thread (`data_out_thread`)**：输出结果合并到的目标线程 ID（默认为 `main`）。
- **Out Desc (`data_out_description`)**：输出数据的描述前缀，用于辅助 LLM 理解数据含义。

#### Task Prompt
- **Task Prompt (`task_prompt`)**：该节点的具体任务指令（Prompt）。若 `llm-first` 节点的 Prompt 为空，则该节点仅执行数据搬运（透传），不消耗 LLM Token。

#### Tools (工具配置)
- **Tools (`tools`)**：选择该节点允许调用的工具集合。
- **Initial Tool (`initial_tool_name`)**：(`tool-first` 节点**必填**) 指定初始运行的工具名称。
- **Initial Args (`initial_tool_args`)**：初始工具调用的参数配置。
- **Enable Tool Loop (`enable_tool_loop`)**：是否允许 LLM 进行多轮工具调用（默认 False）。
- **Tool Limit (`tools_limit`)**：限制特定工具的最大调用次数（例如 `{"web_search": 1}`）。

## 数据流以及其他说明

参考 [llm-linear-executor 文档的 执行顺序](./llm_linear_executor/README.md)

## License

[MIT License](LICENSE) 协议。

# Building a FastMCP Server: A Tutorial

This tutorial walks through creating a simple MCP server using the FastMCP library, based on the examples from the [Pondhouse Data blog post](https://www.pondhouse-data.com/blog/create-mcp-server-with-fastmcp). The server will expose resources to fetch data and a tool to modify a file.

## Prerequisites

Before starting, you need Python installed. Then, set up a virtual environment and install the necessary libraries: `fastmcp` for the server framework and `aiofiles` for asynchronous file operations used in one of the examples.

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
pip install "fastmcp[standard]" aiofiles
```
*Note: The original article used `uv`, but `pip` is more common. `fastmcp[standard]` includes `uvicorn` and `aiofiles`.*

## Basic Server Setup

Create a Python file (e.g., `server.py`) with the following basic FastMCP server setup:

```python
# server.py
from fastmcp import FastMCP

mcp = FastMCP(
    name="Document Assistant",
    instructions="This server allows to fetch and update documents related to PONDHOUSE DATA DOCS."
)

if __name__ == "__main__":
    # Default run mode is STDIO transport
    # mcp.run() 
    
    # We will use SSE transport for network accessibility
    print("Starting server on http://localhost:8000/sse")
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
```

**Explanation:**

*   We import `FastMCP`.
*   We instantiate `FastMCP`, giving it a name and instructions that clients (like LLMs) can use to understand its purpose.
*   The `if __name__ == "__main__":` block makes the script runnable.
*   `mcp.run()` starts the server. By default, it uses `stdio` transport, suitable for local tools.
*   We've configured it to use `sse` (Server-Sent Events) transport, making it accessible over the network on `http://localhost:8000`. The `/sse` path is standard for FastMCP's SSE transport.

## Adding a Resource

Resources provide read-only access to data. Let's add a resource to get application status information.

Add the following code to `server.py` before the `if __name__ == "__main__":` block:

```python
# server.py (additions)
import datetime # Add this import at the top

# ... (FastMCP instantiation) ...

@mcp.resource(
    uri="data://application-information",
    name="ApplicationInfo",
    description="Provides general runtime-information about the application",
    mime_type="application/json",
    tags={"status", "observability"}
)
async def get_application_status() -> dict:
    """Provides general runtime-information about the application"""
    # In a real app, fetch this data dynamically
    return {
          "app_id": "doc-assistant-v1",
          "status": "running",
          "started_at": datetime.datetime.now().isoformat()
     }

# ... (if __name__ == "__main__": block) ...
```

**Explanation:**

*   The `@mcp.resource` decorator registers the `get_application_status` function as an MCP resource.
*   `uri`: A unique identifier for this resource. Clients will use this URI to request the data.
*   `name`, `description`, `tags`: Metadata to help clients understand and categorize the resource. The description defaults to the function's docstring if not provided in the decorator.
*   `mime_type`: Specifies the format of the returned data. FastMCP automatically handles JSON serialization for dictionaries.
*   The function is `async` which is good practice for potentially I/O-bound operations, even though this example is simple.
*   It returns a dictionary, which FastMCP will serialize to JSON.

## Adding a Resource Template

Resource templates allow parts of the URI to be dynamic. Let's add a resource to fetch a user profile based on a user ID.

Add this code to `server.py`:

```python
# server.py (additions)

# ... (get_application_status function) ...

@mcp.resource(
    uri="data://user-profile/{user_id}",
    name="UserProfile",
    description="Gets the user profile information for a specific user_id",
    mime_type="application/json",
    tags={"user", "profile"}
)
async def get_user_profile(user_id: str) -> dict:
    """Gets the user profile information for the given user_id"""
    print(f"Fetching profile for user_id: {user_id}")
    # In a real app, fetch user data from a database or API
    # Example data:
    users = {
        "123": {"user_id": "123", "user_name": "Alice", "email": "alice@example.com"},
        "456": {"user_id": "456", "user_name": "Bob", "email": "bob@example.com"},
    }
    return users.get(user_id, {"error": "User not found", "user_id": user_id})

# ... (if __name__ == "__main__": block) ...
```

**Explanation:**

*   The URI `data://user-profile/{user_id}` includes a placeholder `{user_id}`.
*   FastMCP automatically maps the value provided in this part of the URI by the client to the `user_id` parameter of the function.
*   The function now takes `user_id: str` as an argument.
*   The function simulates looking up user data.

## Adding a Tool

Tools allow clients (like AI agents) to perform actions. Let's add a tool to append text to a file.

Add this code to `server.py`, including necessary imports at the top:

```python
# server.py (additions)
import aiofiles # Add this import
from typing import Annotated # Add this import
from pydantic import Field # Add this import
from fastmcp import Context # Add this import

# ... (FastMCP instantiation and resources) ...

@mcp.tool()
async def edit_file(
    filename: Annotated[ str, Field( description="Path to the target file relative to the server.", min_length=1, max_length=255) ],
    line: Annotated[ str, Field( description="Text content to append to the file.", min_length=1) ],
    ctx: Context, # Added context parameter
    second_line: Annotated[ str, Field( description="Optional second line to append.", min_length=1), ] = ""
    ):
    """
    Asynchronously appends one or two lines of text to the end of a specified file.
    Reports progress via the context.
    """
    await ctx.info(f"Attempting to append to file: {filename}") # Use context for logging
    total_steps = 2 if second_line else 1
    try:
        async with aiofiles.open(filename, mode='a', encoding='utf-8') as file:
            if not line.endswith('\n'):
                line += '\n'
            await file.write(line)
            await ctx.report_progress(progress=1, total=total_steps, message="First line written") # Report progress

            if second_line:
                if not second_line.endswith('\n'):
                    second_line += '\n'
                await file.write(second_line)
                await ctx.report_progress(progress=2, total=total_steps, message="Second line written") # Report progress

        await ctx.info(f"Successfully appended to {filename}")
        # Tools often return None or a confirmation message
        return f"Successfully appended to {filename}" 
    except Exception as e:
        await ctx.error(f"Error appending to file {filename}: {str(e)}") # Use context for errors
        # Re-raise the exception so FastMCP sends an error response to the client
        raise 

# ... (if __name__ == "__main__": block) ...
```

**Explanation:**

*   The `@mcp.tool()` decorator registers the function as a tool. The tool name defaults to the function name (`edit_file`).
*   **Type Hinting and Metadata:**
    *   `Annotated` and `Field` from Pydantic are used to provide detailed descriptions and validation rules (like `min_length`) for parameters. This metadata is crucial for LLMs to understand how to use the tool correctly.
    *   Parameters with default values (`second_line = ""`) are treated as optional by MCP clients.
*   **Context (`ctx: Context`):**
    *   Adding a parameter type-hinted as `Context` gives the function access to MCP features like logging (`ctx.info`, `ctx.error`) and progress reporting (`ctx.report_progress`). These messages are sent back to the connected client.
*   **Async File I/O:** `aiofiles` is used for non-blocking file operations, essential in an async framework like FastMCP.
*   **Error Handling:** Standard Python exceptions are caught, logged via `ctx.error`, and then re-raised. FastMCP converts uncaught exceptions into MCP error responses for the client.
*   **Return Value:** The tool returns a confirmation string upon success. It could also return `None`.

## Running the Server

Ensure your `server.py` file contains all the imports and code snippets above. Then run it from your terminal (make sure your virtual environment is active):

```bash
python server.py
```

You should see output indicating the server is running on `http://localhost:8000/sse`.

## Testing the Server

Create a separate Python file (e.g., `client.py`) to test the server:

```python
# client.py
from fastmcp.client import Client
import asyncio

# URL for the SSE transport
sse_url = "http://localhost:8000/sse" 

client = Client(sse_url)

async def main():
    print(f"Connecting to server at {sse_url}...")
    try:
        async with client:
            print(f"Client connected: {client.is_connected()}")

            # 1. List available tools
            tools = await client.list_tools()
            print("\nAvailable tools:")
            for tool in tools:
                 print(f"- {tool.name}: {tool.description}")

            # 2. List available resources
            resources = await client.list_resources()
            print("\nAvailable resources:")
            for resource in resources:
                 print(f"- {resource.uri}: {resource.description}")

            # 3. Call the 'get_application_status' resource
            print("\nCalling resource 'data://application-information'...")
            app_info = await client.get_resource("data://application-information")
            print(f"Resource result (App Info): {app_info.decode()}") # Decode bytes to string

            # 4. Call the 'get_user_profile' resource template
            user_id_to_get = "123"
            print(f"\nCalling resource 'data://user-profile/{user_id_to_get}'...")
            user_profile = await client.get_resource(f"data://user-profile/{user_id_to_get}")
            print(f"Resource result (User Profile): {user_profile.decode()}")

            user_id_to_get = "999" # Non-existent user
            print(f"\nCalling resource 'data://user-profile/{user_id_to_get}'...")
            user_profile_error = await client.get_resource(f"data://user-profile/{user_id_to_get}")
            print(f"Resource result (User Profile Error): {user_profile_error.decode()}")

            # 5. Call the 'edit_file' tool
            print("\nCalling tool 'edit_file'...")
            if any(tool.name == "edit_file" for tool in tools):
                try:
                    # Setup progress/log handling
                    async def handle_progress(progress, total, message):
                         print(f"  Server Progress: {progress}/{total} - {message}")
                    async def handle_log(level, message):
                         print(f"  Server Log [{level.upper()}]: {message}")
                         
                    client.on_progress(handle_progress)
                    client.on_log(handle_log)

                    result = await client.call_tool(
                        "edit_file",
                        {
                            "filename": "test_output.txt",
                            "line": "Hello from FastMCP client!",
                            "second_line": "This is the second line.",
                        },
                    )
                    # The result from the tool call is often the return value of the tool function
                    print(f"Tool result (edit_file): {result}") 
                except Exception as e:
                    print(f"Tool call failed: {e}") # Catch errors propagated from the server
            else:
                print("Tool 'edit_file' not found.")

    except ConnectionRefusedError:
         print(f"Connection refused. Is the server running at {sse_url}?")
    except Exception as e:
         print(f"An error occurred: {e}")
    finally:
        # Connection is closed automatically by 'async with client'
        print(f"\nClient disconnected: {client.is_connected()}")


if __name__ == "__main__":
    asyncio.run(main())
```

**Explanation:**

*   Imports `Client` from `fastmcp.client` and `asyncio`.
*   Defines the server URL.
*   Creates a `Client` instance.
*   The `async with client:` block handles connection and disconnection.
*   `client.list_tools()` and `client.list_resources()` fetch metadata about available tools and resources.
*   `client.get_resource(uri)` fetches data from a resource endpoint. The result is often bytes and needs decoding.
*   `client.call_tool(tool_name, parameters)` executes a tool on the server.
*   `client.on_progress` and `client.on_log` register callbacks to handle progress and log messages sent from the server via the `Context` object.
*   Error handling is included for connection issues and tool execution errors.

**To Run the Test Client:**

1.  Make sure the `server.py` is running in one terminal.
2.  Open another terminal, activate the same virtual environment (`source .venv/bin/activate`).
3.  Run the client: `python client.py`.

You should see the client connect, list tools/resources, call them, print the results, and display progress/log messages from the `edit_file` tool. A file named `test_output.txt` should be created (or appended to) in the same directory where you ran `server.py`.

This completes the basic setup and testing of a FastMCP server with resources and a tool.

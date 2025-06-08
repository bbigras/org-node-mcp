# This script acts as a FastMCP client for the org-node-mcp server.
# It demonstrates how to connect to the server, list available tools and resources,
# and call specific resources to retrieve information. It's primarily used
# for testing and showcasing the server's API functionality.

from fastmcp.client import Client
import asyncio

# URL for the HTTP transport
# The default FastMCP server runs on HTTP on port 8000
http_url = "http://localhost:8000" 

client = Client(http_url)

async def main():
    print(f"Connecting to server at {http_url}...")
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
            print(f"\nCalling resource 'data://application-information'...")
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

            # Section for calling 'edit_file' tool removed.

    except ConnectionRefusedError:
         print(f"Connection refused. Is the server running at {http_url}?")
    except Exception as e:
         print(f"An error occurred: {e}")
    finally:
        # Connection is closed automatically by 'async with client'
        print(f"\nClient disconnected: {client.is_connected()}")


if __name__ == "__main__":
    asyncio.run(main())

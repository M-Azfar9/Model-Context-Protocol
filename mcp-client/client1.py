import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
import os
from datetime import datetime

load_dotenv()
date = datetime.now()

SERVERS = {
    "expense": {
        "transport": "stdio",
        "command": "C:\\Users\\user\\AppData\\Roaming\\Python\\Python314\\Scripts\\uv.exe",
        "args": [
            "run",
            "fastmcp",
            "run",
            "D:\\Ai Content\\MCP\\Local Servers\\expence-tracker-mcp-server\\main.py"
        ]
    }
}

async def main():
    print("Starting...")
    mcp_client = MultiServerMCPClient(SERVERS)
    tools = await mcp_client.get_tools()
    named_tools = {}
    for tool in tools:
        named_tools[tool.name] = tool   
    
    model = ChatMistralAI(
        model = "mistral-large-latest",
        api_key = os.getenv("MISTRAL_API_KEY"),
    )
    model_with_tools = model.bind_tools(tools) 
    prompt = f"""
    `Today's date is {date}`\n\n
    What is XAI?.
    """
    response = await model_with_tools.ainvoke(prompt)

    if not getattr(response, 'tool_calls',None):
        print(response.content)
        return
        
    selected_tool = response.tool_calls[0]['name']
    selected_tool_id = response.tool_calls[0]['id']
    selected_tool_arguments = response.tool_calls[0]['args']

    print("selected tools: ", selected_tool)
    print("selected arguments: ", selected_tool_arguments)

    # tool_to_call = named_tools[selected_tool]
    # response = await tool_to_call.ainvoke(selected_tool_arguments)
    tool_to_call = named_tools[selected_tool]
    result = await tool_to_call.ainvoke(selected_tool_arguments)
    print("Tool result: ", result)

    tool_message = ToolMessage(content=str(result), name=selected_tool, tool_call_id=selected_tool_id)
    final_response = await model_with_tools.ainvoke([prompt, response, tool_message])
    print("Final response: ", final_response.content)

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import os
import subprocess
from pydantic_ai import Agent, RunContext
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel

# Check if the API key is set
if not os.environ.get('OPENAI_API_KEY'):
    print("Error: OPENAI_API_KEY environment variable is not set.")
    print("Please restart your terminal to load the new environment variables.")
    exit(1)

print("Starting Nemotron Agent...")

# 1. Point to Nemotron 3 Ultra via OpenAI Compat Layer
client = AsyncOpenAI(
    base_url=os.environ.get('OPENAI_API_BASE', 'https://integrate.api.nvidia.com/v1'),
    api_key=os.environ.get('OPENAI_API_KEY')
)

model = OpenAIChatModel(
    model_name='nvidia/nemotron-3-ultra',
    openai_client=client
)

# 2. Define the Agent and its Tools
agent = Agent(
    model, 
    system_prompt="You are an expert software engineer. You have tools to read files, write files, and execute shell commands. Help the user with their programming tasks."
)

@agent.tool
async def read_file(ctx: RunContext[None], path: str) -> str:
    """Reads the contents of a file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

@agent.tool
async def write_file(ctx: RunContext[None], path: str, content: str) -> str:
    """Writes content to a file, overwriting existing content."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {e}"

@agent.tool
async def run_shell(ctx: RunContext[None], cmd: str) -> str:
    """Runs a shell command in the current directory and returns the output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        return output if output else "Command executed successfully (no output)."
    except Exception as e:
        return f"Error running command: {e}"

# 3. Interactive CLI Loop
async def main():
    print("\n--- Nemotron 3 Ultra Agent Active ---")
    print("Type 'exit' or 'quit' to close.")
    
    chat_history = []
    
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.strip().lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                continue
                
            print("\nNemotron is thinking...")
            result = await agent.run(user_input, message_history=chat_history)
            
            print(f"\nNemotron: {result.data}")
            chat_history = result.all_messages()
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())

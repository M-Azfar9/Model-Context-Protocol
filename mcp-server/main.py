from fastmcp import FastMCP
import random

mcp = FastMCP(name="Testing MCP")

@mcp.tool()
def roll_dice(num_dice: int = 1) -> list[int]:
    """Roll a 6-sided dice num_dice times and return the results"""
    return list(random.randint(1, 6) for _ in range(num_dice))

@mcp.tool()
def sum_numbers(numbers: list[int]) -> int:
    """Return the sum of all numbers in the list"""
    return sum(numbers)

if __name__ == "__main__":
    mcp.run(transport="stdio")

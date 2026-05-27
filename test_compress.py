import asyncio
from pathlib import Path
from compress import compress_to_target


async def main():
    input_path = Path("test_input.mp4")
    output_path = Path("storage/temp/test_output.mp4")
    
    print("Starting compression...")
    result = await compress_to_target(input_path, output_path)
    size = result.stat().st_size
    print(f"Done: {result}")
    print(f"Size: {size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    asyncio.run(main())

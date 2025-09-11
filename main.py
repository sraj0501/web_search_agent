import asyncio
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def main():
    return {"message": "Hello World"}

if __name__ == "__main__":
    asyncio.run(main())
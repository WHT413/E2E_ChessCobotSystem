import asyncio
import websockets

class WebSocketClient:
    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        self.port = port
        self.uri = f"ws://{self.host}:{self.port}"
        self.websocket = None

    async def connect(self):
        """Establish WebSocket connection."""
        self.websocket = await websockets.connect(self.uri)
        print(f"Connected to {self.uri}")

    async def send(self, message: str):
        """Send a message to the server."""
        if self.websocket is None:
            raise RuntimeError("WebSocket connection is not established")
        print(f"Sending: {message}")
        await self.websocket.send(message)

    async def receive(self) -> str:
        """Receive a message from the server."""
        if self.websocket is None:
            raise RuntimeError("WebSocket connection is not established")
        response = await self.websocket.recv()
        print(f"Received: {response}")
        return response

    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            print("Connection closed")
            self.websocket = None


async def main():
    client = WebSocketClient(host="10.17.0.238", port=8080)
    await client.connect()
    await client.send("Hello from WebSocket client class!")
    await client.receive()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())

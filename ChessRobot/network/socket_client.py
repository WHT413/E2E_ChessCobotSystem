import asyncio

class TCPClient:
    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.last_message = None

    async def connect(self):
        """Establish TCP connection."""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        print(f"Connected to {self.host}:{self.port}")

    async def send(self, message: str):
        """Send a message to the server."""
        if self.writer is None:
            raise RuntimeError("TCP connection is not established")
        print(f"Sending: {message}")
        if self.last_message != message:
            self.writer.write((message).encode("utf-8"))
            await self.writer.drain()
        else:
            print("Duplicate message, not sending.")
        self.last_message = message

    async def receive(self) -> str:
        """Receive a message from the server."""
        if self.reader is None:
            raise RuntimeError("TCP connection is not established")
        data = await self.reader.readline()
        response = data.decode("utf-8").strip()
        print(f"Received: {response}")
        return response

    async def close(self):
        """Close the TCP connection."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            print("Connection closed")
            self.reader = None
            self.writer = None

async def main():
    client = TCPClient(host="127.0.0.1", port=8080)
    await client.connect()
    await client.send("Hello from TCP client class!")
    await client.receive()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())

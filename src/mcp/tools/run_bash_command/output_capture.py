import asyncio


_ENCODING = "utf-8"

_READ_CHUNK_SIZE_BYTES = 4096


class BoundedOutputBuffer:
    """Keep the beginning and the end of a byte stream, within a fixed size.

    A command can print far more than an agent can read, or than the host
    should hold in memory. This buffer stores at most limit_bytes: the first
    half of the stream and its last half, dropping the middle as data
    arrives. The end is kept because that is where errors and final results
    usually are; the beginning is kept because that is where headers and the
    first error of a cascade usually are.
    """

    def __init__(self, limit_bytes: int) -> None:
        """Create an empty buffer.

        Args:
            limit_bytes: Maximum number of bytes kept, split evenly between
                the beginning and the end of the stream.
        """
        self._head_limit_bytes = limit_bytes // 2
        self._tail_limit_bytes = limit_bytes - self._head_limit_bytes
        self._head = bytearray()
        self._tail = bytearray()
        self._total_size_bytes = 0

    @property
    def is_truncated(self) -> bool:
        """Whether some bytes from the middle of the stream were dropped."""
        return self._total_size_bytes > len(self._head) + len(self._tail)

    def append(self, chunk: bytes) -> None:
        """Add a chunk read from the stream.

        Fills the head first, then keeps only the most recent bytes in the
        tail once the head is full.

        Args:
            chunk: Raw bytes read from the stream.
        """
        self._total_size_bytes += len(chunk)

        head_room_bytes = self._head_limit_bytes - len(self._head)
        if head_room_bytes > 0:
            self._head += chunk[:head_room_bytes]
            chunk = chunk[head_room_bytes:]

        if chunk:
            self._tail += chunk
            overflow_bytes = len(self._tail) - self._tail_limit_bytes
            if overflow_bytes > 0:
                del self._tail[:overflow_bytes]

    def render(self) -> str:
        """Decode the kept bytes, with a marker where the middle was dropped.

        Undecodable bytes (binary output, or a multi-byte character cut at a
        truncation boundary) are replaced rather than raising.

        Returns:
            The captured text.
        """
        if not self.is_truncated:
            return bytes(self._head + self._tail).decode(_ENCODING, errors="replace")

        omitted_bytes = self._total_size_bytes - len(self._head) - len(self._tail)
        head_text = bytes(self._head).decode(_ENCODING, errors="replace")
        tail_text = bytes(self._tail).decode(_ENCODING, errors="replace")
        return f"{head_text}\n[... {omitted_bytes} bytes truncated ...]\n{tail_text}"


async def drain_stream(stream: asyncio.StreamReader, buffer: BoundedOutputBuffer) -> None:
    """Read a subprocess stream until it closes, feeding a bounded buffer.

    Reading continuously (rather than only at the end) is what keeps the
    child from blocking on a full pipe, while the buffer keeps host memory
    bounded whatever the command prints.

    Args:
        stream: stdout or stderr of the subprocess.
        buffer: Buffer receiving the data.
    """
    while chunk := await stream.read(_READ_CHUNK_SIZE_BYTES):
        buffer.append(chunk)

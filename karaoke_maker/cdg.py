"""CD+G encoder (and a small decoder used for previews and tests).

A .cdg file is a stream of 24-byte packets played at 300 packets a second
next to the matching .mp3. The screen is 300x216 pixels in 16 palette
colours, drawn in 6x12 tiles. This module keeps a model of what is on the
screen and turns "make the screen look like this picture at this time" into
the tile packets needed to get there.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

WIDTH = 300
HEIGHT = 216
TILE_W = 6
TILE_H = 12
COLS = WIDTH // TILE_W  # 50
ROWS = HEIGHT // TILE_H  # 18
PACKET_SIZE = 24
PACKETS_PER_SECOND = 300

CDG_COMMAND = 0x09
MEMORY_PRESET = 1
BORDER_PRESET = 2
TILE_BLOCK = 6
LOAD_PALETTE_LOW = 30
LOAD_PALETTE_HIGH = 31
TILE_BLOCK_XOR = 38

EMPTY_PACKET = bytes(PACKET_SIZE)


def packet(instruction: int, data: bytes | list[int]) -> bytes:
    data = bytes(data)
    if len(data) > 16:
        raise ValueError("CD+G packets carry at most 16 data bytes")
    out = bytearray(PACKET_SIZE)
    out[0] = CDG_COMMAND
    out[1] = instruction
    out[4 : 4 + len(data)] = data
    return bytes(out)


def memory_preset(color: int, repeat: int = 0) -> bytes:
    return packet(MEMORY_PRESET, [color & 0x0F, repeat & 0x0F])


def border_preset(color: int) -> bytes:
    return packet(BORDER_PRESET, [color & 0x0F])


def tile_block(row: int, col: int, color0: int, color1: int, bits: list[int], xor: bool = False) -> bytes:
    """One 6x12 tile; bits[y] holds 6 pixels with the leftmost in bit 5."""
    data = [color0 & 0x0F, color1 & 0x0F, row & 0x1F, col & 0x3F] + [b & 0x3F for b in bits]
    return packet(TILE_BLOCK_XOR if xor else TILE_BLOCK, data)


def parse_color(value: str | tuple[int, int, int]) -> tuple[int, int, int]:
    """'#rgb', '#rrggbb' or an (r, g, b) tuple of 0-255 values."""
    if isinstance(value, tuple):
        return value
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"not a colour: {value!r}")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def load_palette(colors: list[tuple[int, int, int]]) -> list[bytes]:
    """Two packets setting all 16 colours (CD+G has 4 bits per channel)."""
    colors = list(colors) + [(0, 0, 0)] * (16 - len(colors))
    out = []
    for half, instruction in ((0, LOAD_PALETTE_LOW), (8, LOAD_PALETTE_HIGH)):
        data = []
        for r, g, b in colors[half : half + 8]:
            r4, g4, b4 = (round(c / 17) for c in (r, g, b))
            data.append((r4 << 2) | (g4 >> 2))
            data.append(((g4 & 0x03) << 4) | b4)
        out.append(packet(instruction, data))
    return out


@dataclass
class _Queued:
    due: int  # packet index this packet should play at, at the earliest
    data: bytes


@dataclass
class CdgWriter:
    """Builds a CD+G stream from screen updates at given times.

    Call :meth:`show` with the picture the screen should have from a time
    on (an 18x50-tile array of palette indices, 300x216). The writer sends
    only the tiles that differ from what is already on screen. Updates must
    be given in time order; packets that don't fit in time run a little
    late rather than being dropped.
    """

    palette: list[tuple[int, int, int]]
    background: int = 0
    packets: list[bytes] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.screen = np.full((HEIGHT, WIDTH), self.background, dtype=np.uint8)
        self._last_time = 0.0
        for p in load_palette(self.palette):
            self.packets.append(p)
        # Preset the screen a few times: some players miss the first one.
        for i in range(4):
            self.packets.append(memory_preset(self.background, i))
        self.packets.append(border_preset(self.background))

    @property
    def lag_seconds(self) -> float:
        """How far the stream has run past the last requested time."""
        return max(0.0, len(self.packets) / PACKETS_PER_SECOND - self._last_time)

    def _pad_to(self, time: float) -> None:
        target = math.floor(time * PACKETS_PER_SECOND)
        if len(self.packets) < target:
            self.packets.extend([EMPTY_PACKET] * (target - len(self.packets)))

    def show(self, time: float, picture: np.ndarray) -> int:
        """Make the screen match picture from time on. Returns packets sent."""
        if picture.shape != (HEIGHT, WIDTH):
            raise ValueError(f"picture must be {HEIGHT}x{WIDTH}")
        time = max(time, self._last_time)
        self._last_time = time
        self._pad_to(time)
        tiles_new = picture.reshape(ROWS, TILE_H, COLS, TILE_W)
        tiles_old = self.screen.reshape(ROWS, TILE_H, COLS, TILE_W)
        changed = np.any(tiles_new != tiles_old, axis=(1, 3))
        sent = 0
        for row, col in zip(*np.nonzero(changed)):
            tile = tiles_new[row, :, col, :]
            self.packets.append(self._tile_packet(int(row), int(col), tile))
            sent += 1
        self.screen = picture.copy()
        return sent

    def _tile_packet(self, row: int, col: int, tile: np.ndarray) -> bytes:
        colors, counts = np.unique(tile, return_counts=True)
        if len(colors) == 1:
            c0 = c1 = int(colors[0])
        else:
            # A tile packet has two colours. Ours never need more; if one
            # does, keep the two most common and round the rest to color0.
            order = np.argsort(-counts)
            c0, c1 = int(colors[order[0]]), int(colors[order[1]])
            if self.background in (c0, c1):
                c1 = c1 if c0 == self.background else c0
                c0 = self.background
            tile = np.where(tile == c1, c1, c0)
        bits = []
        for y in range(TILE_H):
            v = 0
            for x in range(TILE_W):
                if tile[y, x] == c1 and c1 != c0:
                    v |= 1 << (5 - x)
            bits.append(v)
        return tile_block(row, col, c0, c1, bits)

    def finish(self, duration: float) -> bytes:
        """The whole stream, padded to the song's length."""
        self._pad_to(duration)
        return b"".join(self.packets)


class CdgDecoder:
    """Plays a CD+G stream back into a picture (palette indices + RGB)."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pixels = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
        self.palette = [(0, 0, 0)] * 16
        self.position = 0

    @property
    def packet_count(self) -> int:
        return len(self.data) // PACKET_SIZE

    def seek(self, seconds: float) -> None:
        target = min(self.packet_count, math.floor(seconds * PACKETS_PER_SECOND))
        if target < self.position:
            self.__init__(self.data)  # type: ignore[misc]
        while self.position < target:
            self._decode(self.position * PACKET_SIZE)
            self.position += 1

    def rgb(self) -> np.ndarray:
        pal = np.array(self.palette, dtype=np.uint8)
        return pal[self.pixels]

    def _decode(self, o: int) -> None:
        d = self.data
        if d[o] & 0x3F != CDG_COMMAND:
            return
        instruction = d[o + 1] & 0x3F
        data = d[o + 4 : o + 20]
        if instruction == MEMORY_PRESET:
            self.pixels[:] = data[0] & 0x0F
        elif instruction == BORDER_PRESET:
            c = data[0] & 0x0F
            self.pixels[:TILE_H, :] = c
            self.pixels[-TILE_H:, :] = c
            self.pixels[:, :TILE_W] = c
            self.pixels[:, -TILE_W:] = c
        elif instruction in (TILE_BLOCK, TILE_BLOCK_XOR):
            c0, c1 = data[0] & 0x0F, data[1] & 0x0F
            row, col = data[2] & 0x1F, data[3] & 0x3F
            y0, x0 = row * TILE_H, col * TILE_W
            if y0 + TILE_H > HEIGHT or x0 + TILE_W > WIDTH:
                return
            for y in range(TILE_H):
                bits = data[4 + y] & 0x3F
                for x in range(TILE_W):
                    c = c1 if (bits >> (5 - x)) & 1 else c0
                    if instruction == TILE_BLOCK_XOR:
                        c ^= int(self.pixels[y0 + y, x0 + x])
                    self.pixels[y0 + y, x0 + x] = c
        elif instruction in (LOAD_PALETTE_LOW, LOAD_PALETTE_HIGH):
            first = 0 if instruction == LOAD_PALETTE_LOW else 8
            for i in range(8):
                hi, lo = data[i * 2] & 0x3F, data[i * 2 + 1] & 0x3F
                r = (hi >> 2) & 0x0F
                g = ((hi & 0x03) << 2) | ((lo >> 4) & 0x03)
                b = lo & 0x0F
                self.palette[first + i] = (r * 17, g * 17, b * 17)

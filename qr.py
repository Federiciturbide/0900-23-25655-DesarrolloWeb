"""Generador QR Model 2 byte-mode nivel L (versiones 1 a 5, sin dependencias)."""

DATA_CODEWORDS = {1: (19, 7), 2: (34, 10), 3: (55, 15), 4: (80, 20), 5: (108, 26)}
ALIGNMENT = {2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30]}


def _bits(value: int, width: int) -> list[int]:
    return [(value >> index) & 1 for index in range(width - 1, -1, -1)]


def _multiply(x: int, y: int) -> int:
    result = 0
    while y:
        if y & 1:
            result ^= x
        y >>= 1
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    return result


def _generator(degree: int) -> list[int]:
    result = [1]
    root = 1
    for _ in range(degree):
        next_poly = [0] * (len(result) + 1)
        for index, coefficient in enumerate(result):
            next_poly[index] ^= coefficient
            next_poly[index + 1] ^= _multiply(coefficient, root)
        result = next_poly
        root = _multiply(root, 2)
    return result


def _remainder(data: list[int], degree: int) -> list[int]:
    divisor = _generator(degree)
    result = [0] * degree
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for index in range(degree):
            result[index] ^= _multiply(divisor[index + 1], factor)
    return result


def _format_bits(mask: int) -> int:
    # Los bits de nivel de corrección para L son 01.
    data = (0b01 << 3) | mask
    remainder = data << 10
    for bit in range(14, 9, -1):
        if (remainder >> bit) & 1:
            remainder ^= 0x537 << (bit - 10)
    return ((data << 10) | remainder) ^ 0x5412


def encode(text: str) -> list[list[bool]]:
    raw = text.encode("utf-8")
    version = next((v for v, (capacity, _) in DATA_CODEWORDS.items() if len(raw) <= capacity - 2), None)
    if version is None:
        raise ValueError("El texto QR supera la capacidad de 106 bytes.")
    data_count, ecc_count = DATA_CODEWORDS[version]
    stream = [0, 1, 0, 0] + _bits(len(raw), 8)
    for byte in raw:
        stream.extend(_bits(byte, 8))
    capacity_bits = data_count * 8
    stream.extend([0] * min(4, capacity_bits - len(stream)))
    stream.extend([0] * ((-len(stream)) % 8))
    data = [sum(bit << (7 - index) for index, bit in enumerate(stream[pos:pos + 8])) for pos in range(0, len(stream), 8)]
    pad = (0xEC, 0x11)
    pad_index = 0
    while len(data) < data_count:
        data.append(pad[pad_index % 2])
        pad_index += 1
    codewords = data + _remainder(data, ecc_count)

    size = 17 + 4 * version
    matrix: list[list[bool | None]] = [[None] * size for _ in range(size)]
    reserved = [[False] * size for _ in range(size)]

    def set_function(x: int, y: int, value: bool) -> None:
        if 0 <= x < size and 0 <= y < size:
            matrix[y][x] = value
            reserved[y][x] = True

    def finder(cx: int, cy: int) -> None:
        for dy in range(-1, 8):
            for dx in range(-1, 8):
                x, y = cx + dx, cy + dy
                if not (0 <= x < size and 0 <= y < size):
                    continue
                inside = 0 <= dx <= 6 and 0 <= dy <= 6
                black = inside and (dx in (0, 6) or dy in (0, 6) or (2 <= dx <= 4 and 2 <= dy <= 4))
                set_function(x, y, bool(black))

    finder(0, 0)
    finder(size - 7, 0)
    finder(0, size - 7)

    for index in range(8, size - 8):
        set_function(6, index, index % 2 == 0)
        set_function(index, 6, index % 2 == 0)

    if version in ALIGNMENT:
        positions = ALIGNMENT[version]
        for cy in positions:
            for cx in positions:
                if reserved[cy][cx]:
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        set_function(cx + dx, cy + dy, max(abs(dx), abs(dy)) in (0, 2))

    # Reservar celdas de información de formato antes de colocar los datos.
    for index in range(6):
        reserved[index][8] = True
    reserved[7][8] = True
    reserved[8][8] = True
    reserved[8][7] = True
    for col in range(6):
        reserved[8][col] = True
    for index in range(8):
        reserved[8][size - 1 - index] = True
    for index in range(7):
        reserved[size - 7 + index][8] = True
    set_function(8, size - 8, True)

    bits = [((byte >> shift) & 1) for byte in codewords for shift in range(7, -1, -1)]
    bit_index = 0
    upward = True
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            y = size - 1 - vert if upward else vert
            for offset in range(2):
                x = right - offset
                if reserved[y][x]:
                    continue
                bit = bits[bit_index] if bit_index < len(bits) else 0
                bit_index += 1
                if (x + y) % 2 == 0:  # máscara 0
                    bit ^= 1
                matrix[y][x] = bool(bit)
        upward = not upward
        right -= 2

    fmt = _format_bits(0)
    for index in range(6):
        set_function(8, index, bool((fmt >> index) & 1))
    set_function(8, 7, bool((fmt >> 6) & 1))
    set_function(8, 8, bool((fmt >> 7) & 1))
    set_function(7, 8, bool((fmt >> 8) & 1))
    for index in range(9, 15):
        set_function(14 - index, 8, bool((fmt >> index) & 1))
    for index in range(8):
        set_function(size - 1 - index, 8, bool((fmt >> index) & 1))
    for index in range(8, 15):
        set_function(8, size - 15 + index, bool((fmt >> index) & 1))
    set_function(8, size - 8, True)
    return [[bool(cell) for cell in row] for row in matrix]


import socket
import time

PORT = 45678

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 增大Windows接收缓存
sock.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_RCVBUF,
    4 * 1024 * 1024
)

sock.bind(("0.0.0.0", PORT))

print("Waiting for ESP32 UDP data...")

total_bytes = 0
packets = 0
lost = 0

last_sequence = None

start = None
last_packet_time = None

while True:

    sock.settimeout(2)

    try:
        data, addr = sock.recvfrom(65535)
    except socket.timeout:
        if start is not None:
            break
        continue

    now = time.perf_counter()

    if start is None:
        start = now
        print("Receiving from:", addr)

    last_packet_time = now

    total_bytes += len(data)
    packets += 1

    if len(data) >= 4:

        sequence = int.from_bytes(
            data[0:4],
            byteorder="big"
        )

        if last_sequence is not None:

            expected = last_sequence + 1

            if sequence > expected:
                lost += sequence - expected

        last_sequence = sequence

elapsed = last_packet_time - start

mbps = (
    total_bytes * 8 /
    elapsed /
    1_000_000
)

print()
print("===== RESULT =====")
print(f"Received packets : {packets}")
print(f"Lost packets     : {lost}")
print(
    f"Received data    : "
    f"{total_bytes/1024/1024:.2f} MB"
)
print(f"Time             : {elapsed:.2f} s")
print(f"Speed            : {mbps:.2f} Mbps")

if packets + lost > 0:
    loss_rate = lost / (packets + lost) * 100
    print(f"Packet loss      : {loss_rate:.3f}%")
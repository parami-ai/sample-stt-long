"""

Usage:

python test_stt_long.py https://stg-stt.megachat.shop

"""


import os
import sys

import struct
import asyncio
import socketio
import time

sio = socketio.AsyncClient(engineio_logger=False, ssl_verify=False)

if len(sys.argv) > 1:
    endpoint = sys.argv[1]
else:
    raise

if len(sys.argv) > 2:
    api_token = sys.argv[2]
else:
    raise



@sio.event
def disconnect():
    print("disconnected")


@sio.event
async def connect():
    print("connected")


@sio.event
async def speechData(data):
    print("received", data)


with open("samples/20221011080619.wav", "rb") as f:
    wav_content = f.read()

"""
Please follow the following encoding for the audio:

 codec_name:      pcm_s16le
 codec_long_name: PCM signed 16-bit little-endian
 sample_rate:     48000
 bits_per_sample: 16
 
"""

wav_content
# b'RIFF$e\x04...'

wav_header = wav_content[:44]

# Remove the header metadata, and keep just the data
wav_content = wav_content[44:]

print("No. of bytes:", len(wav_content))
# 480000 in bytes


INTERVAL = 0.05
(sample_rate,) = struct.unpack("<I", wav_header[24:28])
BYTES_PER_SECOND = int(sample_rate * 2)


async def main():
    await sio.connect(
        endpoint + "/socket.io",
        transports=["websocket"],
    )

    await sio.emit("authenticate", api_token)

    print(">> startLongStream")

    await sio.emit(
        "startLongStream",
        {
            "config": {
                "rate": sample_rate,  # optional
                "speech_fade_in": 0,  # optional
                "silence_fade_out": 0.6,  # in seconds, optional
                "threshold": 0.0,  # optional
            }
        },
    )

    print(">> streaming")

    # stream the audio wav content by keeping sending "process" with the audio pytes
    chunk_size = 1024
    last_i = 0
    t0 = time.time()
    while True:
        await asyncio.sleep(INTERVAL)
        offset_time = time.time() - t0
        end_byte = int(((offset_time * BYTES_PER_SECOND) // 2) * 2)
        i = end_byte // chunk_size

        while last_i < i:
            chunk = wav_content[last_i * chunk_size : (last_i + 1) * chunk_size]
            if not chunk:
                break
            await sio.emit("binaryData", chunk)
            last_i += 1
        if not chunk:
            break

    for i in range(int(10 / INTERVAL)):
        await sio.emit("binaryData", int(INTERVAL * sample_rate * 2) * b"\x00")
        await asyncio.sleep(INTERVAL)

    await sio.emit("binaryData", wav_content)

    print(">> waiting")

    for _ in range(100):
        # The client does not receive events from the server if not interacting with the server (?)
        await sio.emit("binaryData", b"\x00")
        await asyncio.sleep(0.04)

    print(">> endStream")

    await sio.emit("endStream", "")

    await asyncio.sleep(2)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())

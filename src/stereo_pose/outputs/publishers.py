"""Output publishers / transports (console, JSONL, UDP)."""

from __future__ import annotations

import json
import socket
from abc import ABC, abstractmethod
from pathlib import Path


class Publisher(ABC):
    @abstractmethod
    def publish(self, message: dict):
        pass

    def close(self):
        pass


class ConsolePublisher(Publisher):
    def __init__(self, every_n_frames=1):
        self.every = max(1, int(every_n_frames))

    def publish(self, message):
        if message["frame_index"] % self.every != 0:
            return
        joints = message["joints"]
        parts = []
        for name, data in joints.items():
            xyz = data["xyz_mm"]
            parts.append(f'{name}=({xyz[0]:.0f},{xyz[1]:.0f},{xyz[2]:.0f})')
        print(f'frame={message["frame_index"]} ' + " | ".join(parts))


class JsonlPublisher(Publisher):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = self.path.open("a", encoding="utf-8")

    def publish(self, message):
        self.f.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.f.flush()

    def close(self):
        self.f.close()


class UdpPublisher(Publisher):
    def __init__(self, host, port):
        self.addr = (host, int(port))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def publish(self, message):
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.sock.sendto(payload, self.addr)

    def close(self):
        self.sock.close()


class MultiPublisher(Publisher):
    def __init__(self, publishers):
        self.publishers = list(publishers)

    def publish(self, message):
        for p in self.publishers:
            p.publish(message)

    def close(self):
        for p in self.publishers:
            try:
                p.close()
            except Exception:
                pass


def build_publisher(output_cfg):
    pubs = []

    if output_cfg.get("console", True):
        pubs.append(ConsolePublisher(output_cfg.get("console_every_n_frames", 1)))

    if output_cfg.get("jsonl_file"):
        pubs.append(JsonlPublisher(output_cfg["jsonl_file"]))

    udp = output_cfg.get("udp", {}) or {}
    if udp.get("enabled", False):
        pubs.append(UdpPublisher(udp.get("host", "127.0.0.1"), udp.get("port", 5005)))

    return MultiPublisher(pubs)
import asyncio
from dataclasses import dataclass
import threading

from PySide6.QtCore import QObject, QThread, Signal, Slot
import pypalmsens as ps


@dataclass(frozen=True, slots=True)
class ChannelStatusSnapshot:
    device_state: str
    potential_v: float
    current_ua: float | None = None

    @classmethod
    def from_pypalmsens(cls, status) -> "ChannelStatusSnapshot":
        return cls(
            device_state=str(status.device_state),
            potential_v=float(status.potential),
            current_ua=float(status.current),
        )


class ChannelStatusWorker(QObject):
    status_received = Signal(object)
    failed = Signal(str)

    def __init__(self, instrument):
        super().__init__()
        self.instrument = instrument
        self._stop_requested = threading.Event()

    @Slot()
    def run(self):
        try:
            asyncio.run(self._monitor())
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            QThread.currentThread().quit()

    def request_stop(self):
        self._stop_requested.set()

    async def _monitor(self):
        async with await ps.connect_async(instrument=self.instrument) as manager:
            manager.register_status_callback(self._handle_status)
            try:
                while not self._stop_requested.is_set():
                    await asyncio.sleep(0.1)
            finally:
                manager.unregister_status_callback()

    def _handle_status(self, status):
        self.status_received.emit(ChannelStatusSnapshot.from_pypalmsens(status))

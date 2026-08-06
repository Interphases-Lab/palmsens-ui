from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class channel_status_snapshot:
    device_state: str
    potential_v: float
    current_ua: float | None = None

    @classmethod
    def from_pypalmsens(cls, status) -> "channel_status_snapshot":
        return cls(
            device_state=str(status.device_state),
            potential_v=float(status.potential),
            current_ua=float(status.current),
        )

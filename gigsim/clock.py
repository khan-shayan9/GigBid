"""Simulated clock: sim minutes since the epoch, scaled, plus an admin offset. Persisted."""

from datetime import UTC, datetime, timedelta

from gigsim.db import StateDB


class SimClock:
    def __init__(self, db: StateDB, time_scale: float, epoch: str | None) -> None:
        self._db = db
        self._time_scale = time_scale
        # An env epoch wins; otherwise the first start is remembered so a restart keeps the stream.
        epoch = epoch or db.get_meta("epoch") or datetime.now(UTC).isoformat()
        db.set_meta("epoch", epoch)
        self.epoch = _as_utc(datetime.fromisoformat(epoch))
        # One process owns the clock, so the offset is cached and written through on advance.
        self._offset_min = float(db.get_meta("offset_min") or 0)

    def minutes(self) -> float:
        real_minutes = (datetime.now(UTC) - self.epoch).total_seconds() / 60
        return real_minutes * self._time_scale + self._offset_min

    def advance(self, minutes: float) -> None:
        self._offset_min += minutes
        self._db.set_meta("offset_min", str(self._offset_min))

    def reset(self) -> None:
        """Back to sim minute 0; the epoch never changes, so a fixed GIGSIM_EPOCH stays fixed."""
        self._offset_min = 0.0
        self._offset_min = -self.minutes()
        self._db.set_meta("offset_min", str(self._offset_min))

    def at(self, sim_minutes: float) -> datetime:
        return self.epoch + timedelta(minutes=sim_minutes)


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)

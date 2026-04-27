# event.py — Event dataclass
from dataclasses import dataclass, field


@dataclass
class Event:
    name:               str   = "Event"
    severity:           float = 0.6   # 0.0 (trivial) → 1.0 (catastrophic)
    believability:      float = 0.7   # 0.0 (rumor) → 1.0 (confirmed fact)
    spread_speed:       float = 0.5   # 0.0 (slow) → 1.0 (instant viral)
    authority_response: float = 0.4   # 0.0 (silent) → 1.0 (strong official action)
    event_type:         str   = "social"  # social / disaster / economic / political
    tick_of_onset:      int   = 0
    active:             bool  = field(default=False, init=False)

    def activate(self, current_tick: int) -> bool:
        """Fire the event once tick_of_onset is reached."""
        if not self.active and current_tick >= self.tick_of_onset:
            self.active = True
        return self.active

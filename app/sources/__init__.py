from .base import Source
from .chotot import Chotot
from .manual import parse_manual_text

SOURCES: dict[str, Source] = {s.name: s for s in (Chotot(),)}

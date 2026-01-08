#Samsung Battery Metrics

A Python-based utility to parse Android dumpstate logs, specifically optimized for Samsung devices. This tool extracts power consumption metrics across different system windows to identify battery-draining apps with high-resolution accuracy.
🚀 FeaturesIsolated UID Mapping: Robust association between Android User IDs and Package Names to prevent mapping errors.
Waterfall Timestamping: Automatically tracks and assigns specific time windows (Stats from...) to relevant data sections.
Multi-Table Analysis:Table 1 & 2: Cumulative and Standby (Screen-off) history.
Table 3: Snapshot-based diagnostic windows (4-hour slices).
Table 4: Full session history since the last cable disconnect.Table 
Table 5: Real-time foreground intensity and hourly drain projections.

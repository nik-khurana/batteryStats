# batteryStats

It is perfectly normal for Table 1 (Per-App Stats) and Table 3 (Collector) to show different values even when the window timestamps look identical. This is one of the most confusing parts of Android battery logs, and it comes down to how the data is measured rather than when.

Think of Table 1 as a "Physics Lab" and Table 3 as an "Accounting Spreadsheet."

1. Power Modeling vs. Component Tracking
Table 1 (Per-App Stats): Uses the Power Profile. It looks at hardware events (CPU clock speeds, how many bytes the radio sent, GPS state) and multiplies them by a fixed "cost" defined by Samsung engineers. If the CPU was at 2GHz for 10 seconds, it calculates the mAh based on that specific power draw.

Table 3 (Collector): Uses Battery Fuel Gauge snapshots. It looks at the actual drop in the battery's voltage/coulombs. It then tries to "attribute" that real drop to apps based on their active time.

2. The "Searing/Smearing" of System Services
This is the most common reason for the mismatch.

If an app asks Google Play Services to get its location, Table 1 might attribute that power draw to UID 10025 (Google Play Services).

Table 3 (Collector) is smarter at "cross-referencing." It sees that the request came from Facebook, so it might "smear" or move that power cost over to Facebook’s entry to show you the true cost of that app.

3. Asynchronous Flushing
The Android kernel doesn't update all tables at the exact same millisecond.

Per-App Stats are often updated the moment an app process transitions (like moving from foreground to background).

Batterystats Collector often waits for a specific trigger (like the screen turning off or a timer) to "collect" and summarize the data. If your log was taken right after a heavy burst of use, one table might have the new data while the other hasn't "flushed" its buffer yet.




\n\n\n\n\n


That is an extremely sharp observation. It is counter-intuitive, but you are correct: the bgTime in Table 1 (Per-app stats) and the bgTime in Table 2 (Background stats) will almost never match exactly.

Here is why that happens based on how the Android kernel "slices" time:

1. The "Screen-Off" vs. "Process-Background" Distinction
This is the biggest reason for the discrepancy.

Table 1 (bgTime): This tracks time when an app is not the primary app on your screen. If you are using Spotify while browsing Chrome, Spotify is in the "background" (bgTime) even though your screen is ON.

Table 2 (Background Stats): This section is strictly defined by the Hardware State. It only records data when the Screen is OFF.

Example: If you play music for 1 hour with the screen ON, and 1 hour with the screen OFF:

Table 1 will show 2 hours of bgTime.

Table 2 will only show 1 hour of activity.

2. Differing "Reset" Windows
As you saw in your log, Table 2 often uses a specific diagnostic window (like your 4-hour window), while Table 1 is cumulative since the last time the phone hit 100% charge.

Table 1 is a "Bucket" that keeps filling up all day.

Table 2 is often a "Snapshot" of a specific period of inactivity.

3. The "Smeared" Power Calculation
Android uses a "smearing" algorithm for power. If a system service (like ANDROID_SYSTEM) performs a task on behalf of an app (like a GPS check), the power and time might be "smeared" or attributed differently in the technical background table than in the general per-app ledger.

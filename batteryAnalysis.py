import re
import time
import sys
import os


def analyze_samsung_comprehensive_report(file_path):
    start_perf = time.perf_counter()

    def status(msg):
        sys.stdout.write(f"\r[*] {msg}...")
        sys.stdout.flush()

    if not os.path.exists(file_path):
        print(f"\n[!] Error: File '{file_path}' not found.")
        return

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    uid_map = {}
    sections = {
        "Aggregated_Stats": {},
        "Background_Stats": {},
        "Collector_Diagnostic": [],
        "Collector_Since_Charge": [],
        "Foreground_Report": []
    }

    global_meta = {"Start": "Unknown", "Window": "Unknown Window"}
    since_charge_time = "Unknown Start"

    pkg_pattern = re.compile(r"Package \[([^\]]+)\]")
    id_pattern = re.compile(r"(?:appId|userId)=(\d+)")
    kv_row_re = re.compile(r"^\s*(\d+):\s*([\d\.]+)\s*\((.*?)\)")
    kv_pairs_re = re.compile(r"(\w+)=([\w\s\d\.msdh]+?)(?=\s\w+=|$)")
    fg_row_re = re.compile(
        r"^\s*(\d+)\s*\|\s*(\d+)\s*\|\s*[\d\.]+\s*\|\s*[\d\.]+\s*\|\s*[\d\.]+\s*\|\s*[\d\.]+\s*\|\s*(\d+)\s*\|\s*(.*)")
    coll_row_re = re.compile(r"^\s*(\d+)\s*\|\s*([\d\.]+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*)")

    status(f"Scanning {file_size_mb:.1f}MB log")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        current_pkg = None
        for line in f:
            if "Stats from 20" in line: global_meta["Window"] = line.strip().replace("Stats from ", "")
            if "Start clock time:" in line: global_meta["Start"] = line.split("time:")[1].strip()
            if "Stats since last charge from" in line: since_charge_time = line.strip().replace(
                "Stats since last charge from ", "")
            p_match = pkg_pattern.search(line)
            if p_match: current_pkg = p_match.group(1)
            i_match = id_pattern.search(line)
            if i_match and current_pkg:
                uid_map[i_match.group(1)] = current_pkg
                current_pkg = None

    status("Extracting data")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        mode = None
        for line in f:
            if "Per-app stats:" in line:
                mode = "Aggregated_Stats"
            elif "Per-app stats in background" in line:
                mode = "Background_Stats"
            elif "[Batterystats Collector]" in line:
                mode = "Collector_Diagnostic"
            elif "Stats since last charge from" in line:
                mode = "Collector_Since_Charge"
            elif "[Foreground App Current Report]" in line:
                mode = "Foreground_Report"
            elif "DUMP OF SERVICE" in line:
                mode = None

            if mode in ["Aggregated_Stats", "Background_Stats"]:
                match = kv_row_re.search(line)
                if match:
                    uid, mah, details = match.groups()
                    row = {"uid": uid, "pkg": uid_map.get(uid, f"System:{uid}"), "mah": mah}
                    for k, v in kv_pairs_re.findall(details): row[k] = v.strip()
                    sections[mode][uid] = row
            elif mode in ["Collector_Diagnostic", "Collector_Since_Charge"]:
                c_match = coll_row_re.search(line)
                if c_match:
                    uid, pwr, fg, bg, pkg = c_match.groups()
                    sections[mode].append(
                        {"uid": uid, "mah": pwr, "fg": fg.strip(), "bg": bg.strip(), "pkg": pkg.strip()})
            elif mode == "Foreground_Report":
                f_match = fg_row_re.search(line)
                if f_match:
                    uid, total_uah, dur, pkg_raw = f_match.groups()
                    name = pkg_raw.split('<')[0].strip()
                    sections[mode].append({"uid": uid, "raw_uah": total_uah, "dur": dur, "pkg": name})

    status("Formatting report")
    sys.stdout.write("\r" + " " * 80 + "\r")

    # --- LEGEND & HEADER ---
    print("\n" + "=" * 180)
    print(f"{'DIAGNOSTIC TABLE KEY':^180}")
    print("=" * 180)
    print("Table 1: Per app overall history (Foreground + Background) since last full charge or since when battery stats were reset.")
    print("Table 2: Per app background standby metrics—only records data while the screen was physically OFF.")
    print("Table 3: BatteryStats Collector Diagnostic Summary.")
    print("Table 4: Stats since disconnected from charger ")
    print("Table 5: Foreground App Current Report (Measured uAh and projected mAh drain per hour of active screen use).")
    print("=" * 180)

    print(f"\n{'SAMSUNG POWER DIAGNOSTIC COMPREHENSIVE REPORT':^180}")
    print(f"{'Log Start Time: ' + global_meta['Start']:^180}")
    print("=" * 180)

    render_kv("TABLE 1: PER-APP STATS", sections["Aggregated_Stats"])
    render_kv("TABLE 2: PER-APP STATS (SCREEN-OFF ONLY)", sections["Background_Stats"])
    render_coll(f"TABLE 3: BatteryStats Collector ({global_meta['Window']})", sections["Collector_Diagnostic"])
    render_coll(f"TABLE 4: Since Last Charge Summary ({since_charge_time})", sections["Collector_Since_Charge"])
    render_table_5(sections["Foreground_Report"])

    print(f"\nAnalysis Complete. Execution Time: {time.perf_counter() - start_perf:.4f}s")


# --- RENDERING HELPERS ---
def render_kv(title, data_dict):
    if not data_dict: return
    print(f"\n{title}\n" + "-" * 180)
    header = f"{'UID':<10} | {'Package Name':<60} | {'mAh':<12} | {'FG Time':<12} | {'BG Time':<12} | {'CPU':<10} | {'Wake':<10} | {'Radio':<10}"
    print(header)
    print("-" * 180)
    data = sorted(data_dict.values(), key=lambda x: float(x.get("mah", 0)), reverse=True)
    for r in data:
        print(
            f"{r['uid']:<10} | {r['pkg'][:59]:<60} | {r['mah']:<12} | {r.get('fgTime', '-'):<12} | {r.get('bgTime', '-'):<12} | {r.get('cpu', '-'):<10} | {r.get('wake', '-'):<10} | {r.get('mactive', '-'):<10}")


def render_coll(title, data):
    print(f"\n{title}\n" + "-" * 180)
    header = f"{'UID':<10} | {'Package Name':<60} | {'mAh':<12} | {'Foreground Duration':<35} | {'Background Duration'}"
    print(header)
    print("-" * 180)
    for r in data:
        print(f"{r['uid']:<10} | {r['pkg'][:59]:<60} | {r['mah']:<12} | {r['fg']:<35} | {r['bg']}")


def render_table_5(data_list):
    print(f"\nTABLE 5: Foreground App Current Report\n" + "-" * 180)
    header = f"{'UID':<10} | {'Package Name':<60} | {'Raw uAh':<15} | {'mAh':<12} | {'Secs':<12} | {'Intensity (mAh/s)':<22} | {'1hr Proj'}"
    print(header)
    print("-" * 180)
    for r in sorted(data_list, key=lambda x: int(x['raw_uah']), reverse=True):
        raw = int(r['raw_uah']);
        mah = raw / 1000;
        dur = int(r['dur'])
        intensity = mah / dur if dur > 0 else 0
        print(
            f"{r['uid']:<10} | {r['pkg'][:59]:<60} | {raw:<15} | {mah:<12.2f} | {dur:<12} | {intensity:<22.5f} | {intensity * 3600:<8.1f} mAh")


if __name__ == "__main__":
    analyze_samsung_comprehensive_report('dump.txt')

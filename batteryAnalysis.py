import re, time, sys, os
from datetime import datetime


def analyze_samsung_comprehensive_report(file_path):
    start_perf = time.perf_counter()

    def status(msg):
        sys.stdout.write(f"\r[*] {msg}..."); sys.stdout.flush()

    if not os.path.exists(file_path): return print(f"\n[!] Error: File '{file_path}' not found.")

    uid_map = {}
    sections = {"Aggregated_Stats": {}, "Background_Stats": {}, "Collector_Diagnostic": [],
                "Collector_Since_Charge": [], "Foreground_Report": []}

    meta = {"Start": "Unknown", "DumpTime": "Unknown", "ChargeStart": "Unknown"}
    section_headers = {"Aggregated_Stats": [], "Collector_Since_Charge": []}
    global_window = {"s": "Unknown", "e": "Unknown"}

    pkg_pattern = re.compile(r"Package \[([^\]]+)\]")
    id_pattern = re.compile(r"(?:appId|userId)=(\d+)")
    kv_row_re = re.compile(r"^\s*(\d+):\s*([\d\.]+)\s*\((.*?)\)")
    kv_pairs_re = re.compile(r"(\w+)=([\w\s\d\.msdh]+?)(?=\s\w+=|$)")
    fg_row_re = re.compile(
        r"^\s*(\d+)\s*\|\s*(\d+)\s*\|\s*[\d\.]+\s*\|\s*[\d\.]+\s*\|\s*[\d\.]+\s*\|\s*[\d\.]+\s*\|\s*(\d+)\s*\|\s*(.*)")
    coll_row_re = re.compile(r"^\s*(\d+)\s*\|\s*([\d\.]+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*)")

    def get_duration(s_str, e_str):
        if not s_str or not e_str or "Unknown" in [s_str, e_str]: return "-"
        fmt = "%Y-%m-%d %H:%M:%S" if s_str.count(':') == 2 else "%Y-%m-%d %H:%M"
        try:
            d1 = datetime.strptime(s_str[:19].strip(), fmt)
            d2 = datetime.strptime(e_str[:19].strip(), fmt)
            diff = d2 - d1
            total_secs = diff.total_seconds()
            if total_secs < 0: return "-"
            h, rem = divmod(total_secs, 3600);
            m, _ = divmod(rem, 60)
            return f"{int(h)}h {int(m)}m"
        except:
            return "-"


    status("Mapping UIDs to Packages")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        current_pkg = None
        for line in f:
            if "Start clock time:" in line:
                meta["Start"] = line.split("time:")[1].strip()
                global_window["s"] = meta["Start"]
            if "dumpstate: 20" in line:
                meta["DumpTime"] = line.split("dumpstate:")[1].strip()
                global_window["e"] = meta["DumpTime"]
            p_m, i_m = pkg_pattern.search(line), id_pattern.search(line)
            if p_m: current_pkg = p_m.group(1)
            if i_m and current_pkg:
                uid_map[i_m.group(1)] = current_pkg
                current_pkg = None


    status("Analyzing Logs and Fetching Metrics")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        mode = None
        last_s, last_e = global_window["s"], global_window["e"]

        for line in f:
            if "Stats from 20" in line:
                raw = line.strip().replace("Stats from ", "")
                pts = raw.split(" to ")
                last_s = pts[0].strip()
                last_e = pts[1].strip() if len(pts) > 1 else last_s

            if "Per-app stats:" in line:
                mode = "Aggregated_Stats"
            elif "Per-app stats in background" in line:
                mode = "Background_Stats"
            elif "[Batterystats Collector]" in line:
                mode = "Collector_Diagnostic"
            elif "Stats since last charge from" in line:
                mode = "Collector_Since_Charge"
                meta["ChargeStart"] = line.strip().replace("Stats since last charge from ", "").split('(')[0].strip()
            elif "[Foreground App Current Report]" in line:
                mode = "Foreground_Report"
            elif "DUMP OF SERVICE" in line:
                mode = None

            if mode in ["Aggregated_Stats", "Collector_Since_Charge"]:
                if any(x in line for x in
                       ["Time on battery", "Battery use(%)", "Estimated", "Screen on:", "Mobile radio", "wakelock"]):
                    section_headers[mode if mode == "Aggregated_Stats" else "Collector_Since_Charge"].append(
                        line.strip())

            if mode in ["Aggregated_Stats", "Background_Stats"]:
                m = kv_row_re.search(line)
                if m:
                    uid, mah, details = m.groups()
                    sections[mode][uid] = {
                        "uid": uid, "pkg": uid_map.get(uid, f"Sys:{uid}"), "mah": mah,
                        "s": last_s, "e": last_e, "dur": get_duration(last_s, last_e)
                    }
                    for k, v in kv_pairs_re.findall(details): sections[mode][uid][k] = v.strip()

            elif mode == "Collector_Diagnostic":
                m = coll_row_re.search(line)
                if m:
                    sections[mode].append(
                        {"uid": m.group(1), "mah": m.group(2), "fg": m.group(3).strip(), "bg": m.group(4).strip(),
                         "pkg": m.group(5).strip(),
                         "s": last_s, "e": last_e, "dur": get_duration(last_s, last_e)})

            elif mode == "Collector_Since_Charge":
                m = coll_row_re.search(line)
                if m: sections[mode].append(
                    {"uid": m.group(1), "mah": m.group(2), "fg": m.group(3).strip(), "bg": m.group(4).strip(),
                     "pkg": m.group(5).strip()})

            elif mode == "Foreground_Report":
                m = fg_row_re.search(line)
                if m:
                    sections[mode].append({"uid": m.group(1), "raw_uah": m.group(2), "dur": m.group(3),
                                           "pkg": m.group(4).split('<')[0].strip(),
                                           "s": last_s, "e": last_e, "total_dur": get_duration(last_s, last_e)})

    status("Rendering")
    sys.stdout.write("\r" + " " * 80 + "\r")

    # --- LEGEND & HEADER ---
    print("\n" + "=" * 195)
    print(f"{'DIAGNOSTIC TABLE KEY':^195}")
    print("=" * 195)
    print(
        "Table 1: Per app overall history (FG + BG) since last charge or time battery stats were reset")
    print("Table 2: Per app background standby metrics - only records data while the screen was physically off")
    print(
        "Table 3: Battery Stats Collector Summary")
    print("Table 4: Stats since disconnected from Charger")
    print(
        "Table 5: Foreground App Current Report (calculating projected hourly use of apps in forground)")
    print("=" * 195)

    print(f"\n{'SAMSUNG POWER DIAGNOSTIC COMPREHENSIVE REPORT':^195}")
    print(f"{'Log Finalized: ' + meta['DumpTime']:^195}")
    print("=" * 195)

    # Table 1
    print(f"\nTABLE 1: PER-APP STATS\n" + "-" * 195)
    if section_headers["Aggregated_Stats"]:
        for info in section_headers["Aggregated_Stats"]: print(f"  > {info}")
    render_kv_simple(sections["Aggregated_Stats"])

    # Table 2
    print(f"\nTABLE 2: PER-APP BACKGROUND STATS (SCREEN-OFF ONLY)\n" + "-" * 195)
    render_kv_simple(sections["Background_Stats"])

    # Table 3
    print(f"\nTABLE 3: BATTERY STATS COLLECTOR STATS\n" + "-" * 195)
    print(
        f"{'Start Time':<20} | {'End Time':<20} | {'Dur':<8} | {'UID':<8} | {'Package Name':<55} | {'mAh':<10} | {'Foreground':<15} | {'Background'}\n" + "-" * 195)
    for r in sorted(sections["Collector_Diagnostic"], key=lambda x: (x['e'], float(x['mah'])), reverse=True):
        print(
            f"{r['s']:<20} | {r['e']:<20} | {r['dur']:<8} | {r['uid']:<8} | {r['pkg'][:54]:<55} | {r['mah']:<10} | {r['fg']:<15} | {r['bg']}")

    # Table 4
    print(f"\nTABLE 4: SINCE LAST CHARGE SUMMARY\n" + "-" * 195)
    print(f"Last Disconnected from Charger at: {meta['ChargeStart']}")
    for info in section_headers["Collector_Since_Charge"]: print(f"  > {info}")
    print("-" * 195)
    print(
        f"{'UID':<10} | {'Package Name':<60} | {'mAh':<12} | {'Foreground Duration':<35} | {'Background Duration'}\n" + "-" * 195)
    for r in sections["Collector_Since_Charge"]:
        print(f"{r['uid']:<10} | {r['pkg'][:59]:<60} | {r['mah']:<12} | {r['fg']:<35} | {r['bg']}")

    # Table 5
    peak = render_table_5(sections["Foreground_Report"])
    if peak: print(
        "\n" + "*" * 195 + f"\nIf {peak['pkg']} stays in foreground, it is projected to drain {peak['val']:.1f} mAh/hr.\n" + "*" * 195)

    print(f"\nAnalysis Complete. Time: {time.perf_counter() - start_perf:.4f}s")


def render_kv_simple(data_dict):
    if not data_dict: return
    print(
        f"{'Start Time':<20} | {'End Time':<20} | {'Dur':<8} | {'UID':<8} | {'Package Name':<55} | {'mAh':<10} | {'CPU':<8} | {'Wake':<8}\n" + "-" * 195)
    for r in sorted(data_dict.values(), key=lambda x: float(x.get("mah", 0)), reverse=True):
        print(
            f"{r['s']:<20} | {r['e']:<20} | {r['dur']:<8} | {r['uid']:<8} | {r['pkg'][:54]:<55} | {r['mah']:<10} | {r.get('cpu', '-'):<8} | {r.get('wake', '-'):<8}")


def render_table_5(data_list):
    if not data_list: return None
    print(
        f"\nTABLE 5: FOREGROUND APP CURRENT REPORT\n" + "-" * 195 + f"\n{'Start Time':<20} | {'End Time':<20} | {'Total Dur':<10} | {'UID':<10} | {'Package Name':<50} | {'mAh (uAh/1000)':<10} | {'Secs':<8} | {'Intensity (mAh/s)':<12} | {'1hr Projected drain if app stays in foreground'}\n" + "-" * 195)
    peak = {"pkg": "", "val": 0}
    for r in sorted(data_list, key=lambda x: int(x['raw_uah']), reverse=True):
        m = int(r['raw_uah']) / 1000;
        d = int(r['dur']);
        i = m / d if d > 0 else 0;
        pr = i * 3600
        if pr > peak["val"]: peak = {"pkg": r['pkg'], "val": pr}
        print(
            f"{r['s']:<20} | {r['e']:<20} | {r['total_dur']:<10} | {r['uid']:<10} | {r['pkg'][:49]:<50} | {m:<15f} | {d:<8} | {i:<15f} | {pr:<8.1f} mAh")
    return peak


if __name__ == "__main__":
    analyze_samsung_comprehensive_report('dumpstate.txt')

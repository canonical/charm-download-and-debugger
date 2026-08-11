#!/usr/bin/env python3
import json
import re
import sys
import zipfile
import subprocess
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def read_status_input():
    """Reads juju status content from a file argument or piped stdin."""
    if len(sys.argv) > 1 and sys.argv[1] not in ("-", "--help", "-h"):
        file_path = Path(sys.argv[1])
        if not file_path.is_file():
            print(f"Error: File '{file_path}' not found.")
            sys.exit(1)
        return file_path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        return sys.stdin.read()
    else:
        print("Usage:")
        print("  juju status | ./download_charms.py")
        print("  ./download_charms.py <status_file>")
        sys.exit(1)


def parse_json_or_yaml_status(raw_text):
    """Parses JSON or YAML formatted juju status."""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    if HAS_YAML:
        try:
            parsed = yaml.safe_load(raw_text)
            if isinstance(parsed, dict) and "applications" in parsed:
                return parsed
        except yaml.YAMLError:
            pass

    return None


def parse_tabular_status(raw_text):
    """Parses tabular 'juju status' text by relying on strict column character positions."""
    charms = {}
    lines = raw_text.splitlines()

    in_apps_section = False
    headers_info = []
    
    for line in lines:
        if not line.strip():
            in_apps_section = False
            continue

        # Detect the start of the Applications section
        if re.match(r"^App\s+Version\s+Status", line):
            in_apps_section = True
            headers_info = []
            
            # Map the exact starting index of each header column
            matches = list(re.finditer(r'\S+', line))
            for i, match in enumerate(matches):
                next_start = matches[i+1].start() if i + 1 < len(matches) else None
                headers_info.append({
                    "name": match.group(),
                    "start": match.start(),
                    "next": next_start
                })
            continue

        # Stop parsing apps if we hit a different section (like Units, Machines)
        if in_apps_section and re.match(r"^(Unit|Machine|Storage|Relation|Integration|Offer|SAAS)\s+", line):
            in_apps_section = False
            continue

        if in_apps_section:
            row_data = {}
            # Extract data strictly by character position
            for h in headers_info:
                val = ""
                if h["start"] < len(line):
                    end_idx = h["next"] if h["next"] else len(line)
                    val = line[h["start"]:end_idx].strip()
                row_data[h["name"]] = val

            app_name = row_data.get("App")
            if not app_name:
                continue

            charm_name = row_data.get("Charm")
            channel = row_data.get("Channel")
            rev_str = row_data.get("Rev")

            # Clean up missing data represented by '-' or empty string
            if charm_name == "-": charm_name = None
            if channel == "-": channel = None
            revision = None
            if rev_str and rev_str.isdigit():
                revision = int(rev_str)

            if charm_name:
                key = (charm_name, channel, revision)
                if key not in charms:
                    charms[key] = {
                        "charm_name": charm_name,
                        "channel": channel,
                        "revision": revision,
                        "apps": [app_name]
                    }
                else:
                    charms[key]["apps"].append(app_name)

    return list(charms.values())


def extract_charms_from_structured_data(status_data):
    """Extracts charm metadata from structured JSON/YAML dict."""
    charms = {}
    apps = status_data.get("applications", {})

    for app_name, app_info in apps.items():
        charm_name = app_info.get("charm-name")

        if not charm_name and "charm" in app_info:
            charm_url = app_info["charm"]
            charm_name = charm_url.split("/")[-1].rsplit("-", 1)[0]

        channel = app_info.get("charm-channel") or app_info.get("channel")
        revision = app_info.get("charm-rev") or app_info.get("revision")

        if charm_name:
            key = (charm_name, channel, revision)
            if key not in charms:
                charms[key] = {
                    "charm_name": charm_name,
                    "channel": channel,
                    "revision": revision,
                    "apps": [app_name]
                }
            else:
                charms[key]["apps"].append(app_name)

    return list(charms.values())


def prompt_user_selection(charms):
    """Displays an interactive selection menu."""
    print("\n--- Charms Identified in Juju Status ---")
    for i, item in enumerate(charms, 1):
        rev_str = f"rev {item['revision']}" if item['revision'] is not None else "no rev"
        chan_str = f"channel: {item['channel']}" if item['channel'] else "no channel"
        apps_str = f"apps: {', '.join(item['apps'])}"
        print(f" [{i}] {item['charm_name']} ({chan_str}, {rev_str}) [{apps_str}]")

    print("\nOptions:")
    print(" - Enter numbers separated by commas (e.g., 1, 3)")
    print(" - Enter 'all' to select all charms")
    print(" - Enter 'q' to quit")

    choice = input("\nSelect charms to download: ").strip().lower()

    if choice == "q":
        sys.exit(0)
    elif choice == "all":
        return charms
    else:
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip()]
            return [charms[i] for i in indices if 0 <= i < len(charms)]
        except (ValueError, IndexError):
            print("Invalid selection. Exiting.")
            sys.exit(1)


def download_and_unzip(charm_info, output_dir):
    """Downloads the selected charm revision and unzips it for inspection."""
    charm_name = charm_info["charm_name"]
    revision = charm_info["revision"]
    channel = charm_info["channel"]

    cmd = ["juju", "download", charm_name]

    if revision is not None:
        cmd.extend(["--revision", str(revision)])
    elif channel:
        cmd.extend(["--channel", str(channel)])

    target_dir = output_dir / charm_name
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[+] Downloading '{charm_name}' (Revision: {revision}, Channel: {channel})...")

    try:
        subprocess.run(cmd, cwd=target_dir, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[-] Failed to download {charm_name}. Ensure 'juju' CLI is available in PATH.")
        return

    charm_files = list(target_dir.glob("*.charm"))
    if not charm_files:
        print(f"[-] No .charm file found in {target_dir} post-download.")
        return

    charm_file = charm_files[0]
    extract_path = target_dir / "src"
    extract_path.mkdir(exist_ok=True)

    print(f"[+] Unpacking {charm_file.name} -> {extract_path} ...")
    with zipfile.ZipFile(charm_file, "r") as zip_ref:
        zip_ref.extractall(extract_path)

    print(f"[✓] Code ready at: {extract_path}")


def main():
    raw_status = read_status_input()
    
    structured_data = parse_json_or_yaml_status(raw_status)
    
    if structured_data:
        charms = extract_charms_from_structured_data(structured_data)
    else:
        charms = parse_tabular_status(raw_status)

    if not charms:
        print("No valid charm information could be parsed from the provided status output.")
        sys.exit(1)

    selected_charms = prompt_user_selection(charms)

    if not selected_charms:
        print("No charms selected.")
        sys.exit(0)

    output_base = Path("./downloaded_charms").resolve()
    output_base.mkdir(exist_ok=True)

    for charm_info in selected_charms:
        download_and_unzip(charm_info, output_base)

    print(f"\n" + "=" * 50)
    print(f"Done! Open in VS Code with Copilot using:")
    print(f"  code {output_base}")
    print("=" * 50)


if __name__ == "__main__":
    main()

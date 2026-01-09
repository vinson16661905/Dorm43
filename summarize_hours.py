import argparse
import datetime as dt
import re
from pathlib import Path
from collections import defaultdict

# Extract names by taking the trailing Chinese characters from each role/segment.
NAME_PATTERN = re.compile(r"([\u4e00-\u9fff]{2,4})$")
# Match any time ranges like 18:30-20:00 in a line.
TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def parse_time_ranges(text: str) -> list[tuple[dt.timedelta, str]]:
    """Return a list of (duration, line) for each time range found."""
    ranges: list[tuple[dt.timedelta, str]] = []
    for line in text.splitlines():
        for match in TIME_PATTERN.finditer(line):
            start_h, start_m, end_h, end_m = map(int, match.groups())
            start = dt.timedelta(hours=start_h, minutes=start_m)
            end = dt.timedelta(hours=end_h, minutes=end_m)
            if end < start:
                end += dt.timedelta(days=1)
            ranges.append((end - start, line))
    return ranges


def parse_participants(text: str) -> list[str]:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if "**参与人员：**" in line:
            # The actual names may be on the same line or the next non-empty line.
            header_content = line.replace("**参与人员：**", "").strip()
            candidates = [header_content] if header_content else []
            
            # Check few lines below for names if the list is long or on new lines
            for j in range(idx + 1, min(idx + 5, len(lines))):
                l = lines[j].strip()
                if not l: continue
                if "**" in l and "：" in l: break # Next section
                candidates.append(l)
            
            joined = " ".join(candidates)
            # Split by common Chinese separators or spaces.
            segments = re.split(r"[、，,；;]\s*", joined)
            names: list[str] = []
            for seg in segments:
                seg = seg.strip()
                if not seg:
                    continue
                
                # Remove titles/roles: anything ending in 委员, 主任, 老师, etc.
                # Greedy match to strip the longest prefix that looks like a title.
                clean_name = re.sub(r"^.*(?:楼委会|楼长|指导老师|委员|主任|xx|老师|副主任)\s*", "", seg).strip()
                
                # Extract the name (standard Chinese names are 2-3 characters at the end).
                match = re.search(r"([\u4e00-\u9fff]{2,3})$", clean_name)
                if match:
                    names.append(match.group(1))
            return names
    return []


def collect_logs(root: Path, glob_pattern: str) -> dict[str, dt.timedelta]:
    totals: defaultdict[str, dt.timedelta] = defaultdict(dt.timedelta)
    for file in root.glob(glob_pattern):
        if not file.is_file():
            continue
        text = file.read_text(encoding="utf-8")
        ranges = parse_time_ranges(text)
        participants = parse_participants(text)
        if not participants or not ranges:
            continue
        total_duration = sum((d for d, _ in ranges), dt.timedelta())
        for name in participants:
            totals[name] += total_duration
    return totals


def format_hours(td: dt.timedelta) -> str:
    hours = td.total_seconds() / 3600
    return f"{hours:.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Sum work hours per participant from markdown logs.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Root folder containing markdown logs")
    parser.add_argument("--glob", default="*.md", help="Glob pattern for markdown files")
    args = parser.parse_args()

    totals = collect_logs(args.root, args.glob)
    if not totals:
        print("No data found.")
        return

    print("姓名,工时(小时)")
    for name, duration in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):
        print(f"{name},{format_hours(duration)}")


if __name__ == "__main__":
    main()

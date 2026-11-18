#!/usr/bin/env python3
"""Find personal or machine details before publishing. Prints file names and categories, never the matched value.

    python3 scripts/privacy-check.py                 # files git would publish
    python3 scripts/privacy-check.py --history BASE  # also commits, authors and blobs in BASE..HEAD (or --head REF)
    python3 scripts/privacy-check.py --allow NAME    # permit a public name such as a GitHub handle
"""
import argparse
import getpass
import re
import socket
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "home path": rb"(?:/Users/|/home/)[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\[A-Za-z0-9._-]+",
    "temporary path": rb"/private/(?:tmp|var)/[A-Za-z0-9._/-]+",
    "private network address": rb"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b",
    "hardware address": rb"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b",
    "personal email": rb"[A-Za-z0-9._%+-]+@(?:gmail|icloud|me|mac|outlook|hotmail|yahoo|proton|protonmail)\.[a-z.]+",
    "API token": rb"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b",
    "private key": rb"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
PATTERNS = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
SKIP_NAMES = {"package-lock.json", "uv.lock"}


def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, timeout=10).stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def machine_values(allow):
    vals = {getpass.getuser(), Path.home().name, socket.gethostname(), socket.gethostname().split(".")[0]}
    vals |= {sh("scutil", "--get", n) for n in ("ComputerName", "LocalHostName", "HostName")}
    vals |= {sh("sysctl", "-n", n) for n in ("machdep.cpu.brand_string", "hw.model")}
    vals |= {sh("sw_vers", "-productVersion"), sh("sw_vers", "-buildVersion"), sh("git", "config", "user.name")}
    if "noreply" not in (email := sh("git", "config", "user.email")):
        vals.add(email)
    net = sh("ifconfig")
    vals |= {x for x in re.findall(r"inet6? ([0-9a-fA-F:.]+)", net) if not x.startswith(("127.", "::1", "fe80"))}
    vals |= {x for x in re.findall(r"ether ([0-9a-f:]{17})", net)}
    vals |= set(re.findall(r"gateway: (\S+)", sh("route", "-n", "get", "default")))
    vals |= set(re.findall(r"\bSSID : (.+)", sh("ipconfig", "getsummary", "en0")))
    vals |= set(re.findall(r'"IOPlatform(?:SerialNumber|UUID)" = "([^"]+)"', sh("ioreg", "-rd1", "-c", "IOPlatformExpertDevice")))
    lowered = {a.lower() for a in allow}
    return [v.encode().lower() for v in vals if len(v) >= 4 and v.lower() not in lowered]


def problems(data, machine):
    found = [name for name, rx in PATTERNS.items() if rx.search(data)]
    lower = data.lower()
    return found + ["machine identifier"] * any(v in lower for v in machine)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--allow", action="append", default=[])
    a = ap.parse_args()
    machine, bad = machine_values(a.allow), []
    for name in sh("git", "ls-files", "-co", "--exclude-standard").splitlines():
        p = Path(name)
        if p.is_file() and p.name not in SKIP_NAMES and p.name != "privacy-check.py":
            bad += [f"{name}: {kind}" for kind in problems(p.read_bytes(), machine)]
    if a.history:
        span = f"{a.history}..{a.head}"
        for line in sh("git", "log", "--format=%h%x00%ae%x00%ce%x00%ai%x00%ci%x00%an%x00%cn%x00%B%x01", span).split("\x01"):
            f = line.strip().split("\x00")
            if len(f) < 8:
                continue
            h, ae, ce, ad, cd, an, cn, msg = f[:8]
            if "noreply" not in ae or "noreply" not in ce:
                bad.append(f"commit {h}: author or committer email is not private")
            if not ad.endswith("+0000") or not cd.endswith("+0000"):
                bad.append(f"commit {h}: time zone is visible")
            bad += [f"commit {h} metadata: {kind}" for kind in problems(f"{an}\n{cn}\n{msg}".encode(), machine)]
        objs = sh("git", "rev-list", "--objects", span).splitlines()
        for line in objs:
            parts = line.split(" ", 1)
            if len(parts) == 2 and Path(parts[1]).name not in SKIP_NAMES | {"privacy-check.py"}:
                blob = subprocess.run(["git", "cat-file", "blob", parts[0]], capture_output=True)
                if blob.returncode == 0:
                    bad += [f"history {parts[1]}: {kind}" for kind in problems(blob.stdout, machine)]
    for item in sorted(set(bad)):
        print(item)
    print(f"{len(set(bad))} finding(s).")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

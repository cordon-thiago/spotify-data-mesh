"""Repository hygiene: personal data must not reach the public repository.

Checks that the raw-data folder is ignored by git and that no tracked or
untracked-but-not-ignored text file contains an IPv4 or IPv6 address outside
the reserved ranges the project allows.
"""

import ipaddress
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# RFC 5737 and RFC 3849 documentation ranges, plus loopback and the unspecified address.
ALLOWED_NETWORKS = [
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("2001:db8::/32"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("0.0.0.0/32"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
]
# How real addresses are masked in samples that are pasted into documents.
ALLOWED_TEXT = {"00.000.000.000"}
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
# Candidate IPv6 text: groups of hex digits separated by colons. ipaddress decides if it is real.
IPV6 = re.compile(r"(?<![\w:.])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:.])")
SKIPPED_FILES = re.compile(r"requirements.*\.txt")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=REPO_ROOT)


def is_ignored(path):
    return git("check-ignore", "-q", path).returncode == 0


def candidate_files():
    listing = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    assert listing.returncode == 0, listing.stderr
    for name in filter(None, listing.stdout.split("\0")):
        path = REPO_ROOT / name
        if path.is_file() and not SKIPPED_FILES.fullmatch(path.name):
            yield path


def disallowed_addresses(text):
    for match in [*IPV4.finditer(text), *IPV6.finditer(text)]:
        value = match.group()
        if value in ALLOWED_TEXT:
            continue
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue  # not an IP address, for example a four-part version number or a time of day
        if not any(address in network for network in ALLOWED_NETWORKS):
            yield value


@pytest.mark.parametrize("path", ["data/dummy_export.json", "data/sub/export.json", ".env", ".venv/bin/python"])
def test_local_and_personal_paths_are_ignored(path):
    assert is_ignored(path), f"{path} must be ignored by git"


@pytest.mark.parametrize("path", ["data/README.md", ".env.example", "sample_data/generate.py"])
def test_project_files_are_not_ignored(path):
    assert not is_ignored(path), f"{path} must not be ignored by git"


def test_no_real_ip_address_in_repository_files():
    offences = []
    for path in candidate_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary file
        for number, line in enumerate(text.splitlines(), start=1):
            for value in disallowed_addresses(line):
                offences.append(f"{path.relative_to(REPO_ROOT)}:{number}: {value}")
    assert not offences, "IP addresses outside the allowed ranges:\n" + "\n".join(offences)


def test_scan_detects_a_real_looking_address():
    # Built from parts so this file does not itself contain a public address.
    public = ".".join(["8"] * 4)
    assert list(disallowed_addresses(f"seen at {public} today")) == [public]
    assert list(disallowed_addresses("seen at 192.0.2.7 and 00.000.000.000 and 1.2.3.400")) == []


def test_scan_detects_a_real_looking_ipv6_address():
    public = ":".join(["2606", "4700", "4700", "", "1111"])
    assert list(disallowed_addresses(f"seen at {public} today")) == [public]
    allowed = "2001:db8:1f::2a and ::1 and 12:18:21 and 2025-12-31T12:18:21Z and std::vector"
    assert list(disallowed_addresses(allowed)) == []

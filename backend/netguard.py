"""Fail-closed network guard: refuse any connection that is not loopback.

Stdlib only so it can load before anything else (see sitecustomize.py, which loads it in
every Python child process). Set NETGUARD_ALLOW=host1,host2 to permit specific extra hosts
(e.g. a GPU box on your LAN). Setting NETGUARD=off disables it; do that only to fetch
models, then turn it back on.
"""

import ipaddress
import os
import socket
import sys

_installed = False
_BACKEND = os.path.dirname(os.path.abspath(__file__))


def _extra() -> set:
    return {h.strip().lower() for h in os.environ.get("NETGUARD_ALLOW", "").split(",") if h.strip()}


def host_allowed(host) -> bool:
    if host is None or host == "" or host == b"":
        return True  # wildcard bind / unspecified
    if isinstance(host, bytes):
        host = host.decode("utf-8", "ignore")
    h = str(host).strip("[]").lower()
    if h == "localhost" or h in _extra():
        return True
    try:
        ip = ipaddress.ip_address(h.split("%")[0])
    except ValueError:
        return False
    return ip.is_loopback or ip.is_unspecified


def _check(host) -> None:
    if not host_allowed(host):
        raise OSError(f"netguard: outbound connection to {host!r} blocked (local-only fork)")


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    # Telemetry off and project-scoped model caches, whether or not the guard is on.
    for k, v in {"DO_NOT_TRACK": "true", "SCARF_NO_ANALYTICS": "true", "HF_HUB_DISABLE_TELEMETRY": "1",
                 "ANONYMIZED_TELEMETRY": "False", "GRAPHITI_TELEMETRY_ENABLED": "false",
                 "HF_HOME": os.path.join(_BACKEND, ".models", "hf"),
                 "TIKTOKEN_CACHE_DIR": os.path.join(_BACKEND, ".models", "tiktoken"),
                 "SENTENCE_TRANSFORMERS_HOME": os.path.join(_BACKEND, ".models", "st")}.items():
        os.environ.setdefault(k, v)
    if os.environ.get("NETGUARD", "").lower() == "off":
        print("!" * 70 + "\n!! NETGUARD=off: the local-only network guard is DISABLED in this process.\n"
              "!! Use only for the one-time model download, then unset it.\n" + "!" * 70, file=sys.stderr)
        return
    for k, v in {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}.items():
        os.environ.setdefault(k, v)

    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    real_sendmsg = socket.socket.sendmsg
    real_gethostbyname = socket.gethostbyname
    real_gethostbyname_ex = socket.gethostbyname_ex
    real_gethostbyaddr = socket.gethostbyaddr
    real_getnameinfo = socket.getnameinfo

    def getaddrinfo(host, *a, **kw):
        _check(host)
        return real_getaddrinfo(host, *a, **kw)

    def _addr_ok(sock, address):
        if sock.family == getattr(socket, "AF_UNIX", None):
            return
        if isinstance(address, tuple) and address:
            _check(address[0])

    def connect(self, address):
        _addr_ok(self, address)
        return real_connect(self, address)

    def connect_ex(self, address):
        _addr_ok(self, address)
        return real_connect_ex(self, address)

    def sendto(self, data, *args):
        if args:
            _addr_ok(self, args[-1])
        return real_sendto(self, data, *args)

    def sendmsg(self, buffers, *args, **kw):
        address = args[2] if len(args) > 2 else kw.get("address")
        if address is not None:
            _addr_ok(self, address)
        return real_sendmsg(self, buffers, *args, **kw)

    def gethostbyname(host):
        _check(host)
        return real_gethostbyname(host)

    def gethostbyname_ex(host):
        _check(host)
        return real_gethostbyname_ex(host)

    def gethostbyaddr(host):
        _check(host)
        return real_gethostbyaddr(host)

    def getnameinfo(sockaddr, flags):
        _check(sockaddr[0] if isinstance(sockaddr, tuple) and sockaddr else sockaddr)
        return real_getnameinfo(sockaddr, flags)

    socket.getaddrinfo = getaddrinfo
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    socket.socket.sendmsg = sendmsg
    socket.gethostbyname = gethostbyname
    socket.gethostbyname_ex = gethostbyname_ex
    socket.gethostbyaddr = gethostbyaddr
    socket.getnameinfo = getnameinfo

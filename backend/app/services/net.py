import socket
import threading
from contextlib import contextmanager

_lock = threading.Lock()


@contextmanager
def force_ipv4():
    """Force IPv4 for SMTP/IMAP connections made inside this block.

    Some hosts (seen on Railway) resolve mail servers like smtp.gmail.com to an
    IPv6 address that isn't actually routable from the container, failing with
    "Network is unreachable" even though IPv4 works fine. socket.getaddrinfo is
    process-global, so connections are serialized with a lock to avoid one
    thread restoring it while another is still mid-connect.
    """
    with _lock:
        original_getaddrinfo = socket.getaddrinfo

        def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
            return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = ipv4_only
        try:
            yield
        finally:
            socket.getaddrinfo = original_getaddrinfo

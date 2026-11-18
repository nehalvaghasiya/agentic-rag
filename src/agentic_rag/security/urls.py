"""Host and address SSRF defense for optional external connectors."""

import ipaddress
import socket
from urllib.parse import urlsplit


class UrlPolicy:
    def __init__(self, hosts: set[str]) -> None:
        self.hosts = hosts

    def validate(self, url: str) -> str:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.hostname not in self.hosts:
            raise PermissionError("External URL is not on the allowlist")
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            raise PermissionError("Unsafe external URL")
        for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(item[4][0])
            if not address.is_global:
                raise PermissionError("Private address rejected")
        return url

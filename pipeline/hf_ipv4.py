"""Make every Python connection to Hugging Face use IPv4 (this PC's IPv6 route to CloudFront resets TLS)."""
import socket

_HF_SUFFIXES = (".huggingface.co", ".hf.co")
_orig_getaddrinfo = socket.getaddrinfo


def _is_hf(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    return isinstance(host, str) and (host in ("huggingface.co", "hf.co") or host.endswith(_HF_SUFFIXES))


def _getaddrinfo_ipv4_for_hf(host, port, family=0, type=0, proto=0, flags=0):
    if family in (0, socket.AF_UNSPEC) and _is_hf(host):
        family = socket.AF_INET
    return _orig_getaddrinfo(host, port, family, type, proto, flags)


socket.getaddrinfo = _getaddrinfo_ipv4_for_hf

if __name__ == "__main__":          # python hf_ipv4.py download <repo> [files] --local-dir <dir>  (same as `hf`)
    from huggingface_hub.cli.hf import main
    main()

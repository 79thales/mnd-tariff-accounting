"""Pouze veřejný průzkum MND bez účtu, hesla a exportu cookies.

Čte přihlašovací HTML a odkazy na skripty, nepřihlašuje se. Síťový limit je
20 s a 8 MiB na odpověď. Stažené veřejné skripty slouží jen k prohlédnutí;
nejsou spouštěny. Výstup neprokazuje funkční autentizaci HA adaptéru.
"""

import re
import ssl
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ORIGIN = "https://moje.mnd.cz"
ROOT = Path(__file__).resolve().parents[1] / "output/portal-public"


def fetch(url):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    with urllib.request.urlopen(url, context=context, timeout=20) as response:
        data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("public_response_too_large")
        return data


if __name__ == "__main__":
    html = fetch(ORIGIN + "/login").decode("utf-8")
    ROOT.mkdir(parents=True, exist_ok=True)
    print("Veřejné HTML:", len(html), "znaků")
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', html)
    print("Veřejné skripty:", scripts)
    for index, source in enumerate(scripts):
        url = urljoin(ORIGIN, source)
        if urlsplit(url).netloc != urlsplit(ORIGIN).netloc:
            continue
        data = fetch(url)
        (ROOT / f"public-{index}.js").write_bytes(data)
        print("Načten veřejný skript", index, len(data), "bajtů")

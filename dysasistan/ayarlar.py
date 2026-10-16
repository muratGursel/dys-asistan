"""Kalıcı ayarlar ve dizinler.

Orijinal uygulama ayarları bir .properties dosyasında tutar (LastUserToken,
DefaultScannerDevice, PdfSavePath, ScanMorePagesDialog). Biz de aynı anahtarları
~/.config/dys-asistan/ayarlar.json içinde saklarız. Token saklanmaz.
"""

import json
import os
import threading

from . import PAKET

VARSAYILANLAR = {
    "DefaultScannerDevice": "",     # DYS'ye gösterilen tarayıcı adı
    "ScanMorePagesDialog": True,    # her sayfadan sonra "bir sayfa daha?" sorulsun
    "Resolution": 200,              # dpi
    "Mode": "Gray",                 # Color / Gray / Lineart
    "Source": "",                   # boşsa tarayıcının varsayılanı (çoğunlukla camlı yüzey)
    "PageSize": "A4",               # A4 / A5 / "" (cihazın tüm tarama alanı)
    "AllowedOrigins": [             # tarayıcıdan gelen isteklerde izin verilen kaynaklar
        "https://*.saglik.gov.tr",
        "http://*.saglik.gov.tr",
    ],
}


def yapilandirma_dizini():
    kok = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(kok, PAKET)


def tarama_dizini():
    """Taranan PDF'lerin yeri. Kullanıcıya özel 'Taranan' klasörü (orijinalde 'EbysAgent')."""
    ortam = os.environ.get("DYS_ASISTAN_TARAMA_DIZINI")
    if ortam:
        yol = ortam
    else:
        kok = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        yol = os.path.join(kok, PAKET, "Taranan")
    os.makedirs(yol, exist_ok=True)
    return yol


class Ayarlar:
    def __init__(self, yol=None):
        self.yol = yol or os.path.join(yapilandirma_dizini(), "ayarlar.json")
        self._kilit = threading.Lock()
        self._veri = dict(VARSAYILANLAR)
        try:
            with open(self.yol, encoding="utf-8") as f:
                okunan = json.load(f)
            if isinstance(okunan, dict):
                self._veri.update(okunan)
        except (OSError, ValueError):
            pass

    def oku(self, ad, varsayilan=None):
        with self._kilit:
            return self._veri.get(ad, VARSAYILANLAR.get(ad, varsayilan))

    def yaz(self, ad, deger):
        with self._kilit:
            self._veri[ad] = deger
            try:
                os.makedirs(os.path.dirname(self.yol), exist_ok=True)
                gecici = self.yol + ".tmp"
                with open(gecici, "w", encoding="utf-8") as f:
                    json.dump(self._veri, f, ensure_ascii=False, indent=1)
                os.replace(gecici, self.yol)
            except OSError:
                pass

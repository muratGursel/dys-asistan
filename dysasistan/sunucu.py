"""Yerel HTTP sunucusu: DYS web arayüzünün konuştuğu uç noktalar.

Orijinal EbysAsistan ile aynı adresler, aynı JSON gövdeler, aynı durum kodları ve
aynı Türkçe iletiler kullanılır; DYS tarafında değişiklik gerekmez.

Orijinalden farklar (güvenlik):
- Yalnızca 127.0.0.1 dinlenir (orijinal tüm ağ arayüzlerini dinler).
- Origin başlığı varsa izin listesinde olmalıdır (varsayılan *.saglik.gov.tr);
  yanıtta '*' yerine istek yapan kaynak yazılır.
- Dosya işlemleri (aç, sil, yükle) yalnızca tarama klasörü içindeki yollar için çalışır.
"""

import fnmatch
import json
import logging
import os
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import PORT, __version__, dosyalar, dys, pdf, yazdirma
from .tarama import TaramaHatasi

gunluk = logging.getLogger("dysasistan")

AZAMI_GOVDE = 64 * 1024 * 1024     # StartPrint base64 belge taşıyabilir


class IstekHatasi(Exception):
    def __init__(self, durum, ileti):
        super().__init__(ileti)
        self.durum, self.ileti = durum, ileti


def kaynak_izinli(kaynak, desenler):
    if not kaynak:
        return True            # tarayıcı dışı yerel istemci (curl vb.)
    kaynak = kaynak.strip().rstrip("/").lower()
    if kaynak == "null":
        return False
    return any(fnmatch.fnmatchcase(kaynak, d.lower().rstrip("/")) for d in desenler)


class Uygulama:
    """Uç noktaların iş mantığı. Arayüz geri çağrıları isteğe bağlıdır:
    devam_sor(n) -> bool, yazici_sec(liste, varsayilan, kopya) -> (ad, kopya)|None,
    bildir(baslik, ileti)."""

    def __init__(self, ayarlar, tarayici, devam_sor=None, yazici_sec=None, bildir=None,
                 yukle=dys.yukle, indir=dys.indir):
        self.ayarlar = ayarlar
        self.tarayici = tarayici
        self.devam_sor = devam_sor
        self.yazici_sec = yazici_sec
        self.bildir = bildir or (lambda baslik, ileti: None)
        self._yukle, self._indir = yukle, indir
        self.ek_kaynaklar = []      # --izin-ver ile yalnızca bu oturum için

    def izinli_kaynaklar(self):
        return list(self.ayarlar.oku("AllowedOrigins") or []) + self.ek_kaynaklar

    # Her işleyici (durum, nesne) döndürür; nesne JSON'a çevrilir.
    def IsAlive(self, g):
        if not g.get("token"):
            raise IstekHatasi(400, "Token bulunamadı.")
        return 200, "alive"

    def GetActiveScanners(self, g):
        try:
            liste = self.tarayici.tarayicilar(yenile=bool(g.get("refresh")))
        except Exception:
            gunluk.exception("tarayıcı listesi")
            raise IstekHatasi(500, "Tarayıcı listesi çekilemedi.")
        varsayilan = self.ayarlar.oku("DefaultScannerDevice")
        if liste and not any(t.ad == varsayilan for t in liste):
            varsayilan = liste[0].ad
        return 200, [{"scannerName": t.ad, "isDefault": t.ad == varsayilan} for t in liste]

    def StartScan(self, g):
        try:
            sayfalar = self.tarayici.tara(g.get("scannerName") or "", self.devam_sor)
        except TaramaHatasi as h:
            gunluk.warning("tarama: %s", h)
            raise IstekHatasi(500, str(h) or "Tarayıcıya erişilemedi")
        except Exception:
            gunluk.exception("tarama")
            raise IstekHatasi(500, "Beklenmeyen hata")
        try:
            if not sayfalar:
                raise ValueError("sayfa yok")
            yol = pdf.sayfalardan_pdf(sayfalar, dosyalar.yeni_pdf_yolu(),
                                      dpi=int(self.ayarlar.oku("Resolution") or 200))
        except Exception:
            gunluk.exception("pdf")
            raise IstekHatasi(500, "Tarama dosyası oluşturulamadı.")
        finally:
            pdf.gecici_temizle(sayfalar or [])
        self.bildir("Tarama tamamlandı", "%d sayfa: %s" % (len(sayfalar), os.path.basename(yol)))
        return 200, yol

    def _dosya_islemi(self, islev, g):
        try:
            islev(g.get("path") or "")
        except dosyalar.YolHatasi:
            raise IstekHatasi(400, "Yalnızca tarama klasöründeki dosyalar işlenebilir.")
        except OSError:
            raise IstekHatasi(500, "Dosya işlenirken beklenmeyen hata.")
        return 200, "done"

    def OpenPdf(self, g):
        return self._dosya_islemi(dosyalar.pdf_ac, g)

    def OpenDirectory(self, g):
        if not g.get("path"):
            g = dict(g, path=dosyalar.tarama_dizini())
        return self._dosya_islemi(dosyalar.klasor_ac, g)

    def DeletePdf(self, g):
        return self._dosya_islemi(dosyalar.pdf_sil, g)

    def GetAllFileInfos(self, g):
        return 200, dosyalar.dosya_listesi()

    def UploadPdf(self, g):
        try:
            yol = dosyalar.guvenli_yol(g.get("path") or "")
        except dosyalar.YolHatasi:
            raise IstekHatasi(400, "Yalnızca tarama klasöründeki dosyalar yüklenebilir.")
        if not os.path.isfile(yol):
            raise IstekHatasi(500, "Dosya bulunamadı.")
        try:
            yanit = self._yukle(g.get("apiUrl"), g.get("token"), yol)
        except dys.TokenHatasi as h:
            raise IstekHatasi(500, str(h))
        except urllib.error.HTTPError as h:
            gunluk.warning("yükleme HTTP %s", h.code)
            if h.code == 404:
                raise IstekHatasi(500, "Taranmış dosya, sisteme kaydedilirken bir hata gerçekleşti. (API not found)")
            raise IstekHatasi(500, "Yükleme hatası.")
        except (urllib.error.URLError, OSError) as h:
            gunluk.warning("yükleme: %s", h)
            raise IstekHatasi(500, "Yükleme hatası.")
        except Exception:
            gunluk.exception("yükleme")
            raise IstekHatasi(500, "Dosya işlenirken beklenmeyen hata.")
        return 200, yanit

    def GetActivePrinters(self, g):
        return 200, yazdirma.yazicilar()

    def StartPrint(self, g):
        try:
            yazdirma.yazdir(g, self.yazici_sec, indir=self._indir)
        except yazdirma.YazdirmaIptal:
            raise IstekHatasi(500, "Yazdırma iptal edildi.")
        except yazdirma.YazdirmaHatasi as h:
            gunluk.warning("yazdırma: %s", h)
            if "File Id" in str(h):
                raise IstekHatasi(500, str(h))
            raise IstekHatasi(500, "Yazdırma sürecinde iç hata")
        except Exception:
            gunluk.exception("yazdırma")
            raise IstekHatasi(500, "Yazdırma sürecinde iç hata")
        return 200, "done"


UC_NOKTALAR = ("IsAlive", "GetActiveScanners", "StartScan", "OpenPdf", "OpenDirectory", "DeletePdf",
               "UploadPdf", "GetAllFileInfos", "GetActivePrinters", "StartPrint")


class Isleyici(BaseHTTPRequestHandler):
    server_version = "DysAsistan/" + __version__
    protocol_version = "HTTP/1.1"
    uygulama = None      # sunucu_olustur ayarlar

    def log_message(self, bicim, *arg):
        gunluk.info("%s %s", self.address_string(), bicim % arg)

    # -------------------------------------------------------------- yardımcılar
    def _kaynak(self):
        return self.headers.get("Origin", "")

    def _izinli(self):
        return kaynak_izinli(self._kaynak(), self.uygulama.izinli_kaynaklar())

    def _cors(self):
        kaynak = self._kaynak()
        self.send_header("Access-Control-Allow-Origin", kaynak if kaynak else "*")
        self.send_header("Vary", "Origin")

    def _gonder(self, durum, nesne):
        govde = json.dumps(nesne, ensure_ascii=False).encode("utf-8")
        self.send_response(durum)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self._cors()
        self.end_headers()
        self.wfile.write(govde)

    def _govde(self):
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if uzunluk > AZAMI_GOVDE:
            raise IstekHatasi(413, "İstek çok büyük.")
        ham = self.rfile.read(uzunluk) if uzunluk > 0 else b""
        if not ham.strip():
            return None
        try:
            veri = json.loads(ham.decode("utf-8-sig"))
        except ValueError:
            raise IstekHatasi(400, "Body bulunamadı.")
        return veri if isinstance(veri, dict) else None

    # -------------------------------------------------------------- yöntemler
    def do_OPTIONS(self):
        if not self._izinli():
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         self.headers.get("Access-Control-Request-Headers") or "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _isle(self):
        if not self._izinli():
            gunluk.warning("reddedilen kaynak: %s", self._kaynak())
            return self._gonder(403, "Bu kaynağa izin verilmiyor.")
        ad = self.path.split("?", 1)[0].strip("/")
        if ad not in UC_NOKTALAR:
            return self._gonder(404, "Bulunamadı.")
        try:
            g = self._govde()
            if g is None:
                raise IstekHatasi(400, "Body bulunamadı.")
            if gunluk.isEnabledFor(logging.DEBUG):
                ozet = {k: (("<%d karakter>" % len(v)) if k in ("token", "fileData") and isinstance(v, str) else v)
                        for k, v in g.items()}
                gunluk.debug("%s kaynak=%s tür=%s gövde=%s", ad, self._kaynak() or "-",
                             self.headers.get("Content-Type", "-"), json.dumps(ozet, ensure_ascii=False)[:500])
            durum, nesne = getattr(self.uygulama, ad)(g)
        except IstekHatasi as h:
            durum, nesne = h.durum, h.ileti
        except Exception:
            gunluk.exception(ad)
            durum, nesne = 500, "Beklenmeyen hata"
        if gunluk.isEnabledFor(logging.DEBUG):
            gunluk.debug("%s yanıt %d %s", ad, durum, json.dumps(nesne, ensure_ascii=False)[:300])
        self._gonder(durum, nesne)

    do_GET = do_POST = do_PUT = _isle


def sunucu_olustur(uygulama, adres="127.0.0.1", port=PORT):
    sinif = type("BagliIsleyici", (Isleyici,), {"uygulama": uygulama})
    sunucu = ThreadingHTTPServer((adres, port), sinif)
    sunucu.daemon_threads = True
    return sunucu


def arka_planda_baslat(sunucu):
    t = threading.Thread(target=sunucu.serve_forever, name="dys-sunucu", daemon=True)
    t.start()
    return t

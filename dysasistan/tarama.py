"""SANE ile tarama (scanimage komutu üzerinden).

Orijinal EbysAsistan, Windows'a özgü TWAIN arayüzünü kullanan Asprise kütüphanesiyle
tarar; Linux'ta tarayıcı görmemesinin nedeni budur. Burada SANE kullanılır: USB
tarayıcılar ve ağdaki eSCL/AirScan destekli çok işlevli yazıcılar.

DYS'ye gösterilen ad (scannerName) okunur bir addır ("Kyocera ECOSYS MA4500ix
(192.0.2.162)"); SANE cihaz kimliğine eşleme burada tutulur.
"""

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

LISTE_ZAMAN_ASIMI = 60       # ağ taraması uzun sürebilir
TARAMA_ZAMAN_ASIMI = 180
ONBELLEK_SURESI = 120
SAYFA_BOYUTLARI = {"A4": (210, 297), "A5": (148, 210)}     # mm; "" = cihazın tüm alanı


class TaramaHatasi(RuntimeError):
    """Kullanıcıya gösterilecek Türkçe iletiyle tarama hatası."""


class Tarayici:
    __slots__ = ("cihaz", "ad", "tur")

    def __init__(self, cihaz, ad, tur=""):
        self.cihaz, self.ad, self.tur = cihaz, ad, tur

    def __repr__(self):
        return "Tarayici(%r, %r)" % (self.ad, self.cihaz)


def _ip(cihaz):
    m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", cihaz)
    return m.group(1) if m else ""


def liste_ayristir(cikti):
    """scanimage -f '%d\\t%v\\t%m\\t%t\\n' çıktısını Tarayici listesine çevirir.
    Aynı ağ cihazı hem 'escl' hem 'airscan' ile görünebilir; biri tutulur."""
    tarayicilar, gorulen = [], {}
    for satir in cikti.splitlines():
        parcalar = satir.split("\t")
        if len(parcalar) < 3 or not parcalar[0].strip():
            continue
        cihaz, uretici, model = (p.strip() for p in parcalar[:3])
        # bazı arka uçlar (escl) stdout'a satır sonu olmadan HTTP hata metni basar
        m = re.search(r"(?:escl|airscan|pixma|genesys|hpaio|epson2|epsonds|net|plustek|fujitsu|"
                      r"canon_dr|kodakaio|xerox_mfp|smfp|brother\d*|v4l|test):.*$", cihaz)
        if m:
            cihaz = m.group(0)
        tur = parcalar[3].strip() if len(parcalar) > 3 else ""
        # airscan modele " ip=…" ekler; escl ve airscan üretici yerine "ESCL"/"eSCL" yazar
        ip = _ip(cihaz) or _ip(model) or _ip(tur)
        model = re.sub(r"\s+ip=\S+", "", model)
        if uretici.lower() in ("escl", "wsd"):
            uretici = ""
        if uretici and model.lower().startswith(uretici.lower()):
            ad = model
        else:
            ad = ("%s %s" % (uretici, model)).strip()
        ad = ad.replace("_", " ")
        if ip:
            ad = "%s (%s)" % (ad, ip)
        anahtar = ip or ad
        if anahtar in gorulen:
            # eSCL'yi airscan'e tercih et (scanimage ile daha kararlı)
            onceki = gorulen[anahtar]
            if cihaz.startswith("escl:") and not onceki.cihaz.startswith("escl:"):
                onceki.cihaz = cihaz
            continue
        t = Tarayici(cihaz, ad, tur)
        gorulen[anahtar] = t
        tarayicilar.append(t)
    return tarayicilar


class TaramaYoneticisi:
    def __init__(self, ayarlar, calistir=subprocess.run):
        self.ayarlar = ayarlar
        self._calistir = calistir
        self._kilit = threading.Lock()
        self._liste_kilidi = threading.Lock()
        self._onbellek = None
        self._onbellek_zamani = 0.0

    # ------------------------------------------------------------ liste
    def tarayicilar(self, yenile=False):
        with self._liste_kilidi:
            if (not yenile and self._onbellek is not None
                    and time.monotonic() - self._onbellek_zamani < ONBELLEK_SURESI):
                return list(self._onbellek)
            if not shutil.which("scanimage"):
                raise TaramaHatasi("SANE (scanimage) kurulu değil: sudo apt install sane-utils")
            try:
                sonuc = self._calistir(["scanimage", "-f", "%d\t%v\t%m\t%t\n"], capture_output=True,
                                       text=True, timeout=LISTE_ZAMAN_ASIMI)
            except subprocess.TimeoutExpired:
                raise TaramaHatasi("Tarayıcı listesi zaman aşımına uğradı.")
            self._onbellek = liste_ayristir(sonuc.stdout)
            self._onbellek_zamani = time.monotonic()
            return list(self._onbellek)

    def arka_planda_yenile(self):
        threading.Thread(target=lambda: self._sessiz(self.tarayicilar, True), daemon=True).start()

    @staticmethod
    def _sessiz(islev, *arg):
        try:
            islev(*arg)
        except Exception:
            pass

    def bul(self, ad):
        """DYS'nin gönderdiği adı SANE cihazına çevirir. Ad bir SANE kimliği de olabilir."""
        tarayicilar = self.tarayicilar()
        if not ad:
            ad = self.ayarlar.oku("DefaultScannerDevice")
        for t in tarayicilar:
            if ad and (t.ad == ad or t.cihaz == ad):
                return t
        if not ad and tarayicilar:
            return tarayicilar[0]
        if ad and ":" in ad:          # liste dışında bilinen bir SANE kimliği
            return Tarayici(ad, ad)
        raise TaramaHatasi("Tarayıcı bulunamadı: %s" % (ad or "(tanımlı tarayıcı yok)"))

    # ------------------------------------------------------------ tarama
    def _komut(self, t, cikti, toplu=False, en_az=False):
        komut = ["scanimage", "-d", t.cihaz, "--format=png"]
        if not en_az:
            komut += ["--resolution", str(self.ayarlar.oku("Resolution"))]
            mod = self.ayarlar.oku("Mode")
            if mod:
                komut += ["--mode", mod]
            kaynak = self.ayarlar.oku("Source")
            if kaynak:
                komut += ["--source", kaynak]
            # cihazlar çoğunlukla tüm camı (Legal) tarar; evrak A4
            boyut = SAYFA_BOYUTLARI.get(self.ayarlar.oku("PageSize") or "")
            if boyut:
                komut += ["-x", str(boyut[0]), "-y", str(boyut[1])]
        if toplu:
            komut += ["--batch=" + cikti]
        else:
            komut += ["-o", cikti]
        return komut

    def _tek_tarama(self, t, cikti, toplu=False):
        """Önce ayarlı seçeneklerle, cihaz reddederse en az seçenekle dener."""
        son_hata = ""
        for en_az in (False, True):
            try:
                sonuc = self._calistir(self._komut(t, cikti, toplu, en_az), capture_output=True, text=True,
                                       timeout=TARAMA_ZAMAN_ASIMI)
            except subprocess.TimeoutExpired:
                raise TaramaHatasi("Tarayıcı zaman aşımına uğradı.")
            if sonuc.returncode == 0:
                return
            son_hata = (sonuc.stderr or "").strip().splitlines()[-1:] or [""]
            son_hata = son_hata[0]
            if "invalid argument" not in son_hata.lower() and "invalid" not in son_hata.lower():
                break
        if toplu and "out of documents" in son_hata.lower():
            return
        raise TaramaHatasi("Tarayıcıya erişilemedi: %s" % son_hata if son_hata else "Tarayıcıya erişilemedi.")

    def tara(self, ad, devam_sor=None):
        """Sayfaları tarar ve görüntü dosyalarının listesini döndürür (geçici dizinde).
        devam_sor(sayfa_sayisi) -> bool: bir sayfa daha taransın mı?"""
        if not self._kilit.acquire(blocking=False):
            raise TaramaHatasi("Tarayıcı şu anda başka bir tarama için kullanılıyor.")
        try:
            t = self.bul(ad)
            gecici = tempfile.mkdtemp(prefix="dys-tarama-")
            kaynak = (self.ayarlar.oku("Source") or "").lower()
            sayfalar = []
            if "adf" in kaynak or "feeder" in kaynak or "besleyici" in kaynak:
                self._tek_tarama(t, os.path.join(gecici, "sayfa%03d.png"), toplu=True)
                sayfalar = sorted(os.path.join(gecici, f) for f in os.listdir(gecici) if f.endswith(".png"))
            else:
                while True:
                    yol = os.path.join(gecici, "sayfa%03d.png" % (len(sayfalar) + 1))
                    self._tek_tarama(t, yol)
                    if os.path.exists(yol) and os.path.getsize(yol) > 0:
                        sayfalar.append(yol)
                    if not self.ayarlar.oku("ScanMorePagesDialog") or devam_sor is None:
                        break
                    if not devam_sor(len(sayfalar)):
                        break
            self.ayarlar.yaz("DefaultScannerDevice", t.ad)
            return sayfalar
        finally:
            self._kilit.release()

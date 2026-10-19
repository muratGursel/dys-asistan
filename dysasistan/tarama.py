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


BILGI_SATIRLARI = re.compile(r"rounded value of|^scanning page|^scanned page|^batch terminated|"
                             r"^scanning \d+ pages|^output format", re.I)


def hata_satiri(stderr):
    """scanimage hata çıktısından kullanıcıya gösterilecek satır. 'rounded value of …'
    gibi bilgi satırları asıl hatanın önüne geçmesin."""
    satirlar = [s.strip() for s in (stderr or "").splitlines() if s.strip()]
    anlamli = [s for s in satirlar if not BILGI_SATIRLARI.search(re.sub(r"^scanimage:\s*", "", s))]
    return (anlamli or satirlar or [""])[-1]


def besleyici_adi(kaynak):
    k = (kaynak or "").lower()
    return any(s in k for s in ("adf", "feeder", "besleyici", "duplex"))


class Yetenek:
    """scanimage -A çıktısından gerekenler (mm cinsinden; bilinmiyorsa None)."""

    def __init__(self):
        self.x_max = self.y_max = None
        self.sayfa_gen_max = self.sayfa_yuk_max = None    # canon_dr, fujitsu vb.
        self.kaynaklar, self.kaynak_varsayilan = [], ""

    def alan_secenekleri(self, gen, yuk):
        """İstenen sayfa boyutu için -x/-y (gerekirse önce --page-width/--page-height)
        seçenekleri; değerler cihazın sınırlarına kırpılır."""
        secenekler = []
        if self.sayfa_gen_max is not None or self.sayfa_yuk_max is not None:
            # besleyicili tarayıcılarda tarama alanı sayfa boyuyla sınırlıdır; önce sayfayı büyüt
            if self.sayfa_gen_max is not None:
                gen = min(gen, self.sayfa_gen_max)
                secenekler += ["--page-width", "%g" % gen]
            if self.sayfa_yuk_max is not None:
                yuk = min(yuk, self.sayfa_yuk_max)
                secenekler += ["--page-height", "%g" % yuk]
        else:
            if self.x_max is not None:
                gen = min(gen, self.x_max)
            if self.y_max is not None:
                yuk = min(yuk, self.y_max)
        return secenekler + ["-x", "%g" % gen, "-y", "%g" % yuk]


_ARALIK = re.compile(r"^\s+(-x|-y|--page-width|--page-height)\s+-?[\d.]+\.\.([\d.]+)mm")
_KAYNAK = re.compile(r"^\s+--source\s+(.+?)\s+\[(.*)\]\s*$")


def yetenek_ayristir(cikti):
    y = Yetenek()
    for satir in cikti.splitlines():
        m = _ARALIK.match(satir)
        if m:
            deger = float(m.group(2))
            setattr(y, {"-x": "x_max", "-y": "y_max", "--page-width": "sayfa_gen_max",
                        "--page-height": "sayfa_yuk_max"}[m.group(1)], deger)
            continue
        m = _KAYNAK.match(satir)
        if m:
            y.kaynaklar = [k.strip() for k in m.group(1).split("|") if k.strip()]
            y.kaynak_varsayilan = "" if m.group(2) == "inactive" else m.group(2).strip()
    return y


class TaramaYoneticisi:
    def __init__(self, ayarlar, calistir=subprocess.run):
        self.ayarlar = ayarlar
        self._calistir = calistir
        self._yetenekler = {}
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

    # ------------------------------------------------------------ yetenekler
    def yetenekler(self, t):
        """Cihazın seçeneklerini (scanimage -A) bir kez okur; okunamazsa boş Yetenek."""
        if t.cihaz not in self._yetenekler:
            try:
                sonuc = self._calistir(["scanimage", "-d", t.cihaz, "-A"], capture_output=True, text=True,
                                       timeout=LISTE_ZAMAN_ASIMI)
                y = yetenek_ayristir(sonuc.stdout if sonuc.returncode == 0 else "")
            except (OSError, subprocess.TimeoutExpired):
                y = Yetenek()
            self._yetenekler[t.cihaz] = y
        return self._yetenekler[t.cihaz]

    def besleyici_mi(self, t):
        """Ayarlanan kaynak ya da (ayar boşsa) cihazın varsayılan kaynağı besleyici mi?"""
        kaynak = self.ayarlar.oku("Source") or ""
        if kaynak:
            return besleyici_adi(kaynak)
        y = self.yetenekler(t)
        if y.kaynak_varsayilan:
            return besleyici_adi(y.kaynak_varsayilan)
        # camı olmayan, yalnızca besleyicili cihaz (ör. Canon DR-C225)
        return bool(y.kaynaklar) and all(besleyici_adi(k) for k in y.kaynaklar)

    # ------------------------------------------------------------ tarama
    def _komut(self, t, cikti, toplu=False, en_az=False):
        komut = ["scanimage", "-d", t.cihaz, "--format=png"]
        kaynak = self.ayarlar.oku("Source")
        if kaynak:
            komut += ["--source", kaynak]
        if not en_az:
            komut += ["--resolution", str(self.ayarlar.oku("Resolution"))]
            mod = self.ayarlar.oku("Mode")
            if mod:
                komut += ["--mode", mod]
            # cihazlar çoğunlukla tüm camı (Legal) tarar; evrak A4
            boyut = SAYFA_BOYUTLARI.get(self.ayarlar.oku("PageSize") or "")
            if boyut:
                komut += self.yetenekler(t).alan_secenekleri(*boyut)
        if toplu:
            komut += ["--batch=" + cikti, "--batch-start=%d" % toplu]
        else:
            komut += ["-o", cikti]
        return komut

    def _tek_tarama(self, t, cikti, toplu=0):
        """Önce ayarlı seçeneklerle, başaramazsa en az seçenekle dener.
        toplu > 0 ise besleyiciden toplu tarar; sayfa numarası bu sayıdan başlar."""
        ilk_hata = ""
        for en_az in (False, True):
            try:
                sonuc = self._calistir(self._komut(t, cikti, toplu, en_az), capture_output=True, text=True,
                                       timeout=TARAMA_ZAMAN_ASIMI)
            except subprocess.TimeoutExpired:
                raise TaramaHatasi("Tarayıcı zaman aşımına uğradı.")
            hata = hata_satiri(sonuc.stderr)
            if sonuc.returncode == 0 or (toplu and "out of documents" in (sonuc.stderr or "").lower()):
                return
            ilk_hata = ilk_hata or hata
        raise TaramaHatasi("Tarayıcıya erişilemedi: %s" % ilk_hata if ilk_hata else "Tarayıcıya erişilemedi.")

    def tara(self, ad, devam_sor=None):
        """Sayfaları tarar ve görüntü dosyalarının listesini döndürür (geçici dizinde).
        devam_sor(sayfa_sayisi) -> bool: başka sayfa taransın mı?"""
        if not self._kilit.acquire(blocking=False):
            raise TaramaHatasi("Tarayıcı şu anda başka bir tarama için kullanılıyor.")
        try:
            t = self.bul(ad)
            gecici = tempfile.mkdtemp(prefix="dys-tarama-")
            besleyici = self.besleyici_mi(t)
            sayfalar = []
            while True:
                if besleyici:
                    self._tek_tarama(t, os.path.join(gecici, "sayfa%03d.png"), toplu=len(sayfalar) + 1)
                    sayfalar = sorted(os.path.join(gecici, f) for f in os.listdir(gecici)
                                      if f.endswith(".png") and os.path.getsize(os.path.join(gecici, f)) > 0)
                    if not sayfalar:
                        raise TaramaHatasi("Besleyicide kağıt yok. Belgeyi tarayıcıya yerleştirip yeniden deneyin.")
                else:
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

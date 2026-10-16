"""CUPS ile yazdırma ve evrak barkod etiketi.

StartPrint davranışı (orijinaldeki PrintManager):
- Belge ya gövdede base64 (fileData) gelir ya da DYS'den indirilir (fileId).
- contentType 'application/pdf' / 'application/png' / 'barcode' / diğer.
- 'barcode' için etiket: genel birim, DETSİS birimi, 'tarih - sayı', Code128 barkod,
  oluşturan birim; 72 x 36 mm.
- printerDialog true ise kullanıcıya yazıcı ve kopya sorulur; iptal edilirse hata.
"""

import base64
import datetime
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

from . import code128, dys

ETIKET_MM = (72, 36)
ETIKET_DPI = 300
YAZI_TIPLERI = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]


class YazdirmaIptal(RuntimeError):
    pass


class YazdirmaHatasi(RuntimeError):
    pass


# ------------------------------------------------------------------ yazıcılar

def _lpstat(*arg):
    if not shutil.which("lpstat"):
        return ""
    try:
        return subprocess.run(["lpstat", *arg], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def varsayilan_yazici():
    for satir in _lpstat("-d").splitlines():
        if ":" in satir:
            ad = satir.split(":", 1)[1].strip()
            if ad and "no system default" not in satir.lower():
                return ad
    return ""


def yazicilar():
    """GetActivePrinters yanıtı: [{printerName, isDefault}]"""
    varsayilan = varsayilan_yazici()
    adlar = [s.strip() for s in _lpstat("-e").splitlines() if s.strip()]
    return [{"printerName": a, "isDefault": a == varsayilan} for a in adlar]


# ------------------------------------------------------------------ barkod etiketi

def _yazi_tipi(boyut):
    for yol in YAZI_TIPLERI:
        if os.path.exists(yol):
            return ImageFont.truetype(yol, boyut)
    return ImageFont.load_default()


def _metin(deger):
    """DYS bazı alanları sayı olarak gönderir (code: 987654321)."""
    return "" if deger is None else str(deger).strip()


def etiket_ciz(b):
    """BarcodePrintDto alanlarından etiket görüntüsü (PIL Image, 1 bit)."""
    b = {k: _metin(v) for k, v in b.items() if k != "fileData"}
    mm = ETIKET_DPI / 25.4
    gen, yuk = int(ETIKET_MM[0] * mm), int(ETIKET_MM[1] * mm)
    g = Image.new("1", (gen, yuk), 1)
    c = ImageDraw.Draw(g)
    yazi = _yazi_tipi(int(2.6 * mm))

    def ortala(metin, y):
        metin = _metin(metin).replace("\n", " ").strip()
        if not metin:
            return
        w = c.textlength(metin, font=yazi)
        while w > gen - 2 * mm and len(metin) > 4:
            metin = metin[:-2]
            w = c.textlength(metin + "…", font=yazi)
            if w <= gen - 2 * mm:
                metin += "…"
                break
        c.text(((gen - w) / 2, y), metin, font=yazi, fill=0)

    satir = 3.2 * mm
    y = 1.0 * mm
    ortala(b.get("generalDepartmentName"), y)
    y += satir
    if b.get("detsisDepartmentName"):
        ortala(b.get("detsisDepartmentName"), y)
        y += satir
    tarih_sayi = " - ".join(x for x in (b.get("documentDate"), b.get("documentNumber")) if x)
    ortala(tarih_sayi, y)
    y += satir + 0.5 * mm
    kod = b.get("code", "")
    if kod:
        moduller = code128.encode(kod)
        toplam = sum(moduller)
        modul = max(1, int((gen - 6 * mm) // toplam))   # tam nokta: barkod net okunsun
        x = (gen - toplam * modul) // 2
        bar_yuk = int(9 * mm)
        siyah = True
        for m in moduller:
            if siyah:
                c.rectangle([x, int(y), x + m * modul - 1, int(y) + bar_yuk], fill=0)
            x += m * modul
            siyah = not siyah
        y += bar_yuk + 0.6 * mm
        ortala(kod, y)
        y += satir
    ortala(b.get("creatorDepartmentName"), y)
    return g


# ------------------------------------------------------------------ yazdırma

def _lp(dosya, yazici, kopya, ekler=()):
    if not shutil.which("lp"):
        raise YazdirmaHatasi("CUPS (lp) kurulu değil")
    komut = ["lp", "-n", str(max(1, kopya)), "-t",
             "DYS " + datetime.datetime.now().strftime("%d.%m.%Y %H:%M")]
    if yazici:
        komut += ["-d", yazici]
    for e in ekler:
        komut += ["-o", e]
    sonuc = subprocess.run(komut + [dosya], capture_output=True, text=True, timeout=60)
    if sonuc.returncode != 0:
        raise YazdirmaHatasi((sonuc.stderr or sonuc.stdout).strip() or "lp hata verdi")


def yazdir(istek, yazici_sec=None, indir=dys.indir):
    """StartPrintDto sözlüğünü işler. yazici_sec(yazicilar, varsayilan, kopya) ->
    (yazıcı, kopya) ya da None (iptal)."""
    kopya = int(istek.get("copyCount") or 1)
    yazici = _metin(istek.get("printerName"))
    tur = _metin(istek.get("contentType")).lower()

    if tur == "barcode":
        icerik = None
    elif istek.get("fileData"):
        icerik = base64.b64decode(istek["fileData"])
    elif istek.get("fileId"):
        icerik, gelen_tur = indir(istek.get("apiUrl"), istek.get("token"), istek["fileId"])
        tur = tur or (gelen_tur or "").split(";")[0].strip().lower()
    else:
        raise YazdirmaHatasi("File Id ve File Data bilgilerinden hiç biri gönderilmedi.")

    if istek.get("printerDialog") and yazici_sec:
        secim = yazici_sec(yazicilar(), yazici or varsayilan_yazici(), kopya)
        if not secim:
            raise YazdirmaIptal("Yazdırma iptal edildi.")
        yazici, kopya = secim

    gecici = tempfile.mkdtemp(prefix="dys-yazdir-")
    try:
        if tur == "barcode":
            yol = os.path.join(gecici, "barkod.pdf")
            etiket_ciz(istek).save(yol, "PDF", resolution=float(ETIKET_DPI))
            _lp(yol, yazici, kopya, ["media=Custom.%dx%dmm" % ETIKET_MM, "fit-to-page"])
        else:
            uzanti = {"application/pdf": ".pdf", "application/png": ".png", "image/png": ".png"}.get(tur, "")
            ad = os.path.basename(istek.get("fileName") or "belge" + uzanti)
            yol = os.path.join(gecici, ad if os.path.splitext(ad)[1] else ad + uzanti)
            with open(yol, "wb") as f:
                f.write(icerik)
            _lp(yol, yazici, kopya, ["fit-to-page"] if uzanti == ".png" else [])
    finally:
        shutil.rmtree(gecici, ignore_errors=True)

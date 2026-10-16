"""Tarama klasöründeki PDF'ler: listeleme, açma, silme.

Orijinalden farklı olarak, DYS'den gelen yollar yalnızca tarama klasörü içindeyse
işlenir. Orijinal uygulama her yolu kabul ettiği için, açık bir web sayfası
kullanıcının herhangi bir dosyasını sildirebilirdi.
"""

import datetime
import os
import subprocess

from .ayarlar import tarama_dizini


class YolHatasi(ValueError):
    """İstenen yol tarama klasörünün dışında."""


def guvenli_yol(yol, kok=None):
    kok = os.path.realpath(kok or tarama_dizini())
    gercek = os.path.realpath(yol or "")
    if gercek != kok and not gercek.startswith(kok + os.sep):
        raise YolHatasi(yol)
    return gercek


def _tr_sayi(deger):
    """Java DecimalFormat("#.##") Türkçe yerelde: 0,12 / 1,5 / 3"""
    metin = ("%.2f" % deger).rstrip("0").rstrip(".")
    return metin.replace(".", ",")


def zaman_metni(zaman=None):
    """Orijinaldeki biçim: dd.MM.yyyy HH:mm:ss"""
    zaman = zaman or datetime.datetime.now()
    return zaman.strftime("%d.%m.%Y %H:%M:%S")


def yeni_pdf_yolu(kok=None):
    """doc_<dd.MM.yyyy HH:mm:ss>.pdf; orijinal ':' ve ' ' karakterlerini değiştirir."""
    kok = kok or tarama_dizini()
    ad = "doc_" + zaman_metni().replace(":", ".").replace(" ", "_") + ".pdf"
    yol = os.path.join(kok, ad)
    n = 1
    while os.path.exists(yol):
        n += 1
        yol = os.path.join(kok, ad[:-4] + "_%d.pdf" % n)
    return yol


def dosya_listesi(kok=None):
    """GetAllFileInfos yanıtı: [{size, name, path, creationTime}], yeniden eskiye."""
    kok = kok or tarama_dizini()
    sonuc = []
    try:
        adlar = os.listdir(kok)
    except OSError:
        return sonuc
    for ad in adlar:
        if not ad.lower().endswith(".pdf"):
            continue
        yol = os.path.join(kok, ad)
        try:
            bilgi = os.stat(yol)
        except OSError:
            continue
        mb = bilgi.st_size / (1024.0 * 1024.0)
        olusma = getattr(bilgi, "st_birthtime", None) or bilgi.st_mtime
        sonuc.append({
            "size": _tr_sayi(mb) + " MB",
            "name": ad,
            "path": yol,
            "creationTime": zaman_metni(datetime.datetime.fromtimestamp(olusma)),
            "_zaman": olusma,
        })
    sonuc.sort(key=lambda d: d["_zaman"], reverse=True)
    for d in sonuc:
        del d["_zaman"]
    return sonuc


def _xdg_ac(yol):
    subprocess.Popen(["xdg-open", yol], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def pdf_ac(yol):
    gercek = guvenli_yol(yol)
    if os.path.isfile(gercek):
        _xdg_ac(gercek)


def klasor_ac(yol):
    gercek = guvenli_yol(yol)
    if os.path.exists(gercek):
        _xdg_ac(os.path.dirname(gercek) if os.path.isfile(gercek) else gercek)


def pdf_sil(yol):
    gercek = guvenli_yol(yol)
    if os.path.isfile(gercek):
        os.remove(gercek)

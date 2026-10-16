"""Taranan sayfaları tek PDF'te birleştirme."""

import os
import shutil

from PIL import Image


def sayfalardan_pdf(sayfalar, cikti, dpi=200):
    """Görüntü dosyalarını sırasıyla tek PDF'e yazar. Renkli/gri sayfalar JPEG olarak
    gömülür (PIL), böylece dosya boyutu küçük kalır."""
    if not sayfalar:
        raise ValueError("sayfa yok")
    goruntuler = []
    for yol in sayfalar:
        g = Image.open(yol)
        g.load()
        if g.mode in ("RGBA", "P", "LA", "I;16", "I"):
            g = g.convert("RGB")
        goruntuler.append(g)
    ilk, kalan = goruntuler[0], goruntuler[1:]
    gecici = cikti + ".yapiliyor"
    ilk.save(gecici, "PDF", resolution=float(dpi), save_all=True, append_images=kalan)
    os.replace(gecici, cikti)
    for g in goruntuler:
        g.close()
    return cikti


def gecici_temizle(sayfalar):
    dizinler = {os.path.dirname(s) for s in sayfalar}
    for d in dizinler:
        if os.path.basename(d).startswith("dys-tarama-"):
            shutil.rmtree(d, ignore_errors=True)

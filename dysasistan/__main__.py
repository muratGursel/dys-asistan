"""Komut satırı girişi: dys-asistan [--sunucu-yalniz | --tarayicilari-listele | --surum]"""

import argparse
import json
import logging
import os
import signal
import sys
import urllib.request

from . import AD, PORT, __version__
from .ayarlar import Ayarlar, yapilandirma_dizini
from .tarama import TaramaHatasi, TaramaYoneticisi


def calisiyor_mu(port=PORT):
    """Aynı portta bir DYS Asistan zaten yanıt veriyor mu?"""
    istek = urllib.request.Request("http://127.0.0.1:%d/IsAlive" % port, method="POST",
                                   data=json.dumps({"token": "-"}).encode(),
                                   headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(istek, timeout=2) as y:
            return json.loads(y.read().decode("utf-8")) == "alive"
    except Exception:
        return False


def _gunluk_kur(ayrintili):
    os.makedirs(yapilandirma_dizini(), exist_ok=True)
    isleyiciler = [logging.StreamHandler()]
    try:
        isleyiciler.append(logging.FileHandler(os.path.join(yapilandirma_dizini(), "gunluk.txt"), encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=logging.DEBUG if ayrintili else logging.INFO, handlers=isleyiciler,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("PIL").setLevel(logging.INFO)     # eklenti yükleme satırları günlüğü boğuyor


def main(argv=None):
    p = argparse.ArgumentParser(prog="dys-asistan", description="%s: DYS için tarama ve yazdırma yardımcısı" % AD)
    p.add_argument("--sunucu-yalniz", action="store_true", help="arayüz olmadan yalnızca yerel sunucuyu çalıştır")
    p.add_argument("--tarayicilari-listele", action="store_true", help="bulunan tarayıcıları yaz ve çık")
    p.add_argument("--izin-ver", action="append", default=[], metavar="KAYNAK",
                   help="bu oturumda ek bir web kaynağına izin ver (örn. http://localhost:8000)")
    p.add_argument("--port", type=int, default=PORT, help=argparse.SUPPRESS)
    p.add_argument("--ayrintili", action="store_true", help="ayrıntılı günlük")
    p.add_argument("--surum", "--version", action="version", version="%s %s" % (AD, __version__))
    a = p.parse_args(argv)

    ayarlar = Ayarlar()
    tarayici = TaramaYoneticisi(ayarlar)

    if a.tarayicilari_listele:
        try:
            for t in tarayici.tarayicilar(yenile=True):
                print("%s\t%s" % (t.ad, t.cihaz))
        except TaramaHatasi as h:
            print(h, file=sys.stderr)
            return 1
        return 0

    _gunluk_kur(a.ayrintili)
    if calisiyor_mu(a.port):
        print("%s zaten çalışıyor." % AD, file=sys.stderr)
        return 0

    from .sunucu import Uygulama, arka_planda_baslat, sunucu_olustur

    if a.sunucu_yalniz:
        # ekransız denemede DYS'nin istediği yazıcı seçimi bu kuyruğa yönlendirilir
        zorla = os.environ.get("DYS_ASISTAN_YAZICI_ZORLA")
        uygulama = Uygulama(ayarlar, tarayici,
                            yazici_sec=(lambda liste, varsayilan, kopya: (zorla, kopya)) if zorla else None)
    else:
        from .arayuz import Arayuz
        ui = Arayuz(ayarlar, tarayici)
        uygulama = Uygulama(ayarlar, tarayici, devam_sor=ui.devam_sor, yazici_sec=ui.yazici_sec, bildir=ui.bildir)

    uygulama.ek_kaynaklar = a.izin_ver
    try:
        sunucu = sunucu_olustur(uygulama, port=a.port)
    except OSError as h:
        print("Port %d açılamadı (%s). Başka bir uygulama kullanıyor olabilir." % (a.port, h), file=sys.stderr)
        return 2
    logging.getLogger("dysasistan").info("%s %s dinleniyor: 127.0.0.1:%d", AD, __version__, a.port)
    tarayici.arka_planda_yenile()      # ilk listeleme ağda uzun sürebilir

    if a.sunucu_yalniz:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            sunucu.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0

    arka_planda_baslat(sunucu)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    ui.calistir()
    sunucu.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

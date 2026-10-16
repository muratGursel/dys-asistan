"""GTK3 arayüzü: sistem çekmecesi simgesi, "bir sayfa daha?" sorusu, yazıcı seçimi,
ayarlar penceresi.

HTTP istekleri ayrı iş parçacıklarında gelir; GTK çağrıları GLib.idle_add ile ana
döngüye aktarılır ve yanıt bir threading.Event ile beklenir.
"""

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import AD, UYGULAMA_KIMLIGI, __version__, dosyalar  # noqa: E402

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
except (ValueError, ImportError):
    AppIndicator = None

SIMGE = "scanner"
COZUNURLUKLER = (100, 150, 200, 300, 400, 600)
MODLAR = (("Gray", "Gri"), ("Color", "Renkli"), ("Lineart", "Siyah-beyaz"))
BOYUTLAR = (("A4", "A4"), ("A5", "A5"), ("", "Tarayıcının tüm alanı"))


def ana_dongude(islev, *arg):
    """islev'i GTK ana döngüsünde çalıştırır ve sonucunu bekler."""
    if threading.current_thread() is threading.main_thread():
        return islev(*arg)
    bitti, sonuc = threading.Event(), {}

    def calistir():
        try:
            sonuc["deger"] = islev(*arg)
        except Exception as h:      # hata çağırana taşınır
            sonuc["hata"] = h
        bitti.set()
        return False

    GLib.idle_add(calistir)
    bitti.wait()
    if "hata" in sonuc:
        raise sonuc["hata"]
    return sonuc.get("deger")


def _en_onde(pencere):
    pencere.set_keep_above(True)
    pencere.set_position(Gtk.WindowPosition.CENTER)
    pencere.present()


class Arayuz:
    def __init__(self, ayarlar, tarayici):
        self.ayarlar, self.tarayici = ayarlar, tarayici
        self._ayar_penceresi = None
        self._simge_kur()

    # -------------------------------------------------------------- çekmece
    def _menu(self):
        menu = Gtk.Menu()
        for etiket, islev in (("Taranan belgeler klasörü", self._klasor),
                              ("Ayarlar…", self.ayarlari_goster),
                              ("Hakkında", self._hakkinda),
                              (None, None),
                              ("Çıkış", lambda *_: Gtk.main_quit())):
            if etiket is None:
                menu.append(Gtk.SeparatorMenuItem())
                continue
            oge = Gtk.MenuItem(label=etiket)
            oge.connect("activate", islev)
            menu.append(oge)
        menu.show_all()
        return menu

    def _simge_kur(self):
        self._menu_nesnesi = self._menu()
        if AppIndicator is not None:
            self._gosterge = AppIndicator.Indicator.new(UYGULAMA_KIMLIGI, SIMGE,
                                                        AppIndicator.IndicatorCategory.APPLICATION_STATUS)
            self._gosterge.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self._gosterge.set_title(AD)
            self._gosterge.set_menu(self._menu_nesnesi)
        else:
            self._gosterge = Gtk.StatusIcon.new_from_icon_name(SIMGE)
            self._gosterge.set_tooltip_text("%s — çalışıyor" % AD)
            self._gosterge.connect("activate", self.ayarlari_goster)
            self._gosterge.connect("popup-menu", lambda s, d, z: self._menu_nesnesi.popup(
                None, None, Gtk.StatusIcon.position_menu, s, d, z))

    def _klasor(self, *_):
        dosyalar.klasor_ac(dosyalar.tarama_dizini())

    def _hakkinda(self, *_):
        d = Gtk.AboutDialog(program_name=AD, version=__version__, logo_icon_name=SIMGE,
                            comments="DYS için Pardus tarama ve yazdırma yardımcısı",
                            license_type=Gtk.License.GPL_3_0)
        d.run()
        d.destroy()

    # -------------------------------------------------------------- HTTP geri çağrıları
    def devam_sor(self, sayfa):
        return ana_dongude(self._devam_sor, sayfa)

    def _devam_sor(self, sayfa):
        d = Gtk.MessageDialog(message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE,
                              text="%d sayfa tarandı." % sayfa)
        d.set_title(AD)
        d.format_secondary_text("Sonraki sayfayı tarayıcıya yerleştirip devam edebilirsiniz.")
        d.add_button("Bitir", Gtk.ResponseType.NO)
        d.add_button("Bir sayfa daha tara", Gtk.ResponseType.YES)
        d.set_default_response(Gtk.ResponseType.YES)
        _en_onde(d)
        yanit = d.run()
        d.destroy()
        return yanit == Gtk.ResponseType.YES

    def yazici_sec(self, liste, varsayilan, kopya):
        return ana_dongude(self._yazici_sec, liste, varsayilan, kopya)

    def _yazici_sec(self, liste, varsayilan, kopya):
        d = Gtk.Dialog(title="Yazdır — " + AD)
        d.add_button("İptal", Gtk.ResponseType.CANCEL)
        d.add_button("Yazdır", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.OK)
        izgara = Gtk.Grid(row_spacing=8, column_spacing=12, margin=12)
        secici = Gtk.ComboBoxText()
        for y in liste:
            secici.append(y["printerName"], y["printerName"])
        if varsayilan:
            secici.set_active_id(varsayilan)
        if secici.get_active() < 0 and liste:
            secici.set_active(0)
        adet = Gtk.SpinButton.new_with_range(1, 99, 1)
        adet.set_value(kopya)
        izgara.attach(Gtk.Label(label="Yazıcı", xalign=0), 0, 0, 1, 1)
        izgara.attach(secici, 1, 0, 1, 1)
        izgara.attach(Gtk.Label(label="Kopya", xalign=0), 0, 1, 1, 1)
        izgara.attach(adet, 1, 1, 1, 1)
        d.get_content_area().add(izgara)
        d.show_all()
        _en_onde(d)
        yanit = d.run()
        secim = (secici.get_active_id() or "", int(adet.get_value()))
        d.destroy()
        return secim if yanit == Gtk.ResponseType.OK and secim[0] else None

    def bildir(self, baslik, ileti):
        GLib.idle_add(self._bildir, baslik, ileti)

    def _bildir(self, baslik, ileti):
        try:
            gi.require_version("Notify", "0.7")
            from gi.repository import Notify
            if not Notify.is_initted():
                Notify.init(AD)
            Notify.Notification.new(baslik, ileti, SIMGE).show()
        except (ValueError, ImportError, GLib.Error):
            pass
        return False

    # -------------------------------------------------------------- ayarlar
    def ayarlari_goster(self, *_):
        if self._ayar_penceresi:
            self._ayar_penceresi.present()
            return
        p = Gtk.Window(title="Ayarlar — " + AD)
        p.set_default_size(460, -1)
        p.connect("destroy", lambda *_: setattr(self, "_ayar_penceresi", None))
        self._ayar_penceresi = p

        izgara = Gtk.Grid(row_spacing=10, column_spacing=12, margin=16)
        p.add(izgara)

        self._tarayici_secici = Gtk.ComboBoxText(hexpand=True)
        yenile = Gtk.Button.new_from_icon_name("view-refresh", Gtk.IconSize.BUTTON)
        yenile.set_tooltip_text("Tarayıcıları yeniden ara")
        yenile.connect("clicked", lambda *_: self._tarayicilari_doldur(True))
        satir = Gtk.Box(spacing=6)
        satir.pack_start(self._tarayici_secici, True, True, 0)
        satir.pack_start(yenile, False, False, 0)

        cozunurluk = Gtk.ComboBoxText()
        for c in COZUNURLUKLER:
            cozunurluk.append(str(c), "%d dpi" % c)
        cozunurluk.set_active_id(str(self.ayarlar.oku("Resolution")))

        mod = Gtk.ComboBoxText()
        for kimlik, etiket in MODLAR:
            mod.append(kimlik, etiket)
        mod.set_active_id(self.ayarlar.oku("Mode") or "Gray")

        boyut = Gtk.ComboBoxText()
        for kimlik, etiket in BOYUTLAR:
            boyut.append(kimlik, etiket)
        boyut.set_active_id(self.ayarlar.oku("PageSize") or "")

        kaynak = Gtk.Entry(text=self.ayarlar.oku("Source") or "",
                           placeholder_text="Boş: tarayıcının varsayılanı (örn. Flatbed, ADF)")

        sor = Gtk.CheckButton(label="Her sayfadan sonra \"bir sayfa daha?\" diye sor")
        sor.set_active(bool(self.ayarlar.oku("ScanMorePagesDialog")))

        for i, (etiket, nesne) in enumerate((("Tarayıcı", satir), ("Çözünürlük", cozunurluk),
                                             ("Renk", mod), ("Sayfa", boyut), ("Kaynak", kaynak))):
            izgara.attach(Gtk.Label(label=etiket, xalign=0), 0, i, 1, 1)
            izgara.attach(nesne, 1, i, 1, 1)
        izgara.attach(sor, 0, 5, 2, 1)

        klasor = Gtk.Label(xalign=0, selectable=True, wrap=True)
        klasor.set_markup("<small>Taranan belgeler: %s</small>" % GLib.markup_escape_text(dosyalar.tarama_dizini()))
        izgara.attach(klasor, 0, 6, 2, 1)

        def kaydet(*_):
            if self._tarayici_secici.get_active_id():
                self.ayarlar.yaz("DefaultScannerDevice", self._tarayici_secici.get_active_id())
            self.ayarlar.yaz("Resolution", int(cozunurluk.get_active_id() or 200))
            self.ayarlar.yaz("Mode", mod.get_active_id() or "Gray")
            self.ayarlar.yaz("PageSize", boyut.get_active_id() or "")
            self.ayarlar.yaz("Source", kaynak.get_text().strip())
            self.ayarlar.yaz("ScanMorePagesDialog", sor.get_active())
            p.destroy()

        dugmeler = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        vazgec = Gtk.Button(label="Vazgeç")
        vazgec.connect("clicked", lambda *_: p.destroy())
        tamam = Gtk.Button(label="Kaydet")
        tamam.get_style_context().add_class("suggested-action")
        tamam.connect("clicked", kaydet)
        dugmeler.pack_start(vazgec, False, False, 0)
        dugmeler.pack_start(tamam, False, False, 0)
        izgara.attach(dugmeler, 0, 7, 2, 1)

        p.show_all()
        self._tarayicilari_doldur(False)

    def _tarayicilari_doldur(self, yenile):
        secici = self._tarayici_secici
        secici.remove_all()
        secici.append("", "Aranıyor…")
        secici.set_active(0)

        def is_parcasi():
            try:
                liste = self.tarayici.tarayicilar(yenile=yenile)
            except Exception:
                liste = []
            GLib.idle_add(doldur, liste)

        def doldur(liste):
            if self._ayar_penceresi is None:
                return False
            secici.remove_all()
            for t in liste:
                secici.append(t.ad, t.ad)
            if not liste:
                secici.append("", "Tarayıcı bulunamadı")
            secici.set_active_id(self.ayarlar.oku("DefaultScannerDevice"))
            if secici.get_active() < 0:
                secici.set_active(0)
            return False

        threading.Thread(target=is_parcasi, daemon=True).start()

    def calistir(self):
        Gtk.main()

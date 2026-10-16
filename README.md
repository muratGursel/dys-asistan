# DYS Asistan

Türkçe · **[English](README.en.md)**

Sağlık Bakanlığı DYS'de **taramanın ve barkod yazdırmanın Pardus'ta
çalışmasını** sağlayan yerel yardımcı.

DYS'nin "Tara" düğmesi, bilgisayarda çalışan bir yardımcı programla
(EbysAsistan) konuşur. Bakanlığın dağıttığı yardımcı yalnızca Windows'ta
tarayıcı görebildiği için Pardus kullanan birimler tarama yapamıyordu. Bu
program, aynı yerel adresi ve aynı istek biçimlerini kullanan bağımsız bir
yeniden yazımdır. **DYS tarafında hiçbir değişiklik gerekmez.**

> **Resmî bir Bakanlık ürünü değildir.** Bağımsız, açık kaynak bir uyumluluk
> çalışmasıdır; Bakanlığın yazılımından kod içermez.

> **Durum: erken sürüm (0.1).** Pardus 25'te gerçek DYS ile tarama (tek ve
> çok sayfa), DYS'ye yükleme ve barkod etiketi yazdırma denendi. Farklı
> tarayıcı ve yazıcılarla ilgili sonuçlarınızı
> [Issues](https://github.com/muratGursel/dys-asistan/issues) sayfasında
> paylaşırsanız çok yardımcı olur.

## Neler yapar

- **Tarama:** USB tarayıcılar ve ağdaki çok işlevli yazıcılar (eSCL/AirScan,
  WSD). Tarayıcı adları DYS'de okunur biçimde görünür:
  `Kyocera ECOSYS MA4500ix (192.0.2.162)`.
- **Çok sayfalı belge:** her sayfadan sonra "bir sayfa daha?" diye sorar;
  sayfalar tek PDF'te birleşir. Belge besleyicili (ADF) cihazlarda tüm
  sayfalar tek seferde taranabilir.
- **A4:** cihaz tüm camı tarasa bile sayfa A4 olarak kaydedilir (ayarlanabilir).
- **DYS'ye yükleme:** taranan belge DYS'nin isteğiyle kendiliğinden eke düşer.
- **Barkod etiketi:** DYS'deki "Barkod yazdır" ile evrak bilgileri ve
  Code 128 barkodu içeren 72×36 mm etiket; yazıcı ve kopya sayısı seçilebilir.
- **Belge yazdırma:** DYS'den gelen PDF ve görüntüler CUPS ile basılır.
- Oturum açıldığında sistem çekmecesinde kendiliğinden başlar.

## Güvenlik

Orijinal yardımcıdan farklı olarak:

- Yalnızca bu bilgisayardan erişilebilir (`127.0.0.1`); ağdaki başka
  bilgisayarlar bağlanamaz.
- Yalnızca `*.saglik.gov.tr` adreslerindeki sayfaların isteklerini kabul eder;
  başka bir web sitesi tarayıcıyı ya da dosyalarınızı kullanamaz.
- Açma, silme ve yükleme yalnızca tarama klasöründeki dosyalar için çalışır.
- DYS oturum bilgisi (token) diske yazılmaz.

## Kurulum (Pardus 23 / 25, Debian tabanlı sistemler)

```sh
curl -fsSL https://raw.githubusercontent.com/muratGursel/dys-asistan/main/install.sh | sudo sh
```

Ya da [Sürümler](https://github.com/muratGursel/dys-asistan/releases)
sayfasından `dys-asistan_*_all.deb` dosyasını indirip kurun:

```sh
sudo apt install ./dys-asistan_*_all.deb
```

Kurulumdan sonra oturumu kapatıp açın ya da menüden **DYS Asistan**'ı
başlatın. Windows'tan gelen EbysAsistan ile aynı portu kullandığı için ikisi
aynı anda çalışmaz.

Ağ tarayıcıları için `sane-airscan` paketi önerilir (kurulumla gelir).

## Kullanım

Ayrıntılar: [docs/KULLANIM.md](docs/KULLANIM.md)

1. Çekmecedeki simgeden **Ayarlar…** ile varsayılan tarayıcıyı seçin.
2. DYS'de **Tara**'ya basın; tarayıcıyı seçin.
3. Her sayfadan sonra **Bir sayfa daha tara** ya da **Bitir**.

Tarayıcınız listede yoksa uçbirimde `dys-asistan --tarayicilari-listele`
komutunun çıktısına bakın; burada görünmeyen bir cihazı DYS de göremez.

## Geliştirme

[docs/GELISTIRME.md](docs/GELISTIRME.md)

## Lisans

GPL-3.0-or-later. Bkz. [LICENSE](LICENSE).

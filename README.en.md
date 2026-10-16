# DYS Asistan

**[Türkçe](README.md)** · English

A local helper that makes **scanning and barcode printing work on Pardus**
in DYS, the document management system of the Turkish Ministry of Health.

DYS's "Scan" button talks to a helper program running on the user's
computer (EbysAsistan). The helper distributed by the Ministry can only see
scanners on Windows, so units using Pardus could not scan. This program is
an independent reimplementation that serves the same local address with the
same request formats. **No change is needed on the DYS side.**

> **Not an official Ministry product.** It is an independent, open source
> compatibility project and contains no code from the Ministry's software.

> **Status: early release (0.1).** Tested on Pardus 25 against the real DYS:
> single and multi-page scanning, upload to DYS and barcode label printing.

## Features

- **Scanning** through SANE: USB scanners and network multifunction printers
  (eSCL/AirScan, WSD).
- **Multi-page documents:** asks "one more page?" after each page; pages are
  merged into one PDF. ADF devices can scan all pages at once.
- Pages are saved as **A4** even when the device scans its whole glass.
- **Upload to DYS** when DYS asks for it.
- **Barcode labels** (72×36 mm, Code 128) and **document printing** via CUPS,
  with a printer and copy count dialog.
- Starts automatically in the system tray at login.

## Security

Unlike the original helper, it listens on `127.0.0.1` only, accepts requests
only from `*.saglik.gov.tr` pages, limits open/delete/upload to files in its
scan folder and never writes the DYS session token to disk.

## Installation (Pardus 23 / 25, Debian based systems)

```sh
curl -fsSL https://raw.githubusercontent.com/muratGursel/dys-asistan/main/install.sh | sudo sh
```

or download `dys-asistan_*_all.deb` from
[Releases](https://github.com/muratGursel/dys-asistan/releases) and run
`sudo apt install ./dys-asistan_*_all.deb`.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

#!/bin/bash
# dotty v2 — pypff installer
# by jLaHire
#
# pypff (libpff) doesn't ship on pip. this script builds it from source
# with python bindings. needed for PST/OST email parsing.
#
# usage: bash install_pypff.sh

set -e

DEPS="automake autoconf libtool pkg-config gcc make python3-dev gettext autopoint"

echo "[*] installing build dependencies..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq $DEPS git
elif command -v dnf &>/dev/null; then
    sudo dnf install -y automake autoconf libtool pkgconfig gcc make python3-devel git gettext-devel
elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm automake autoconf libtool pkgconf gcc make python git gettext
elif command -v brew &>/dev/null; then
    brew install automake autoconf libtool pkg-config gettext
else
    echo "[!] unknown package manager — install build tools manually"
    exit 1
fi

WORKDIR=$(mktemp -d)
echo "[*] cloning libpff into $WORKDIR..."
git clone --depth 1 https://github.com/libyal/libpff.git "$WORKDIR/libpff"
cd "$WORKDIR/libpff"

echo "[*] syncing dependencies..."
./synclibs.sh

echo "[*] running autogen..."
./autogen.sh

echo "[*] configuring with python bindings..."
./configure --enable-python

echo "[*] building..."
make -j$(nproc 2>/dev/null || echo 2)

echo "[*] installing..."
sudo make install
sudo ldconfig 2>/dev/null || true

echo "[*] verifying..."
python3 -c "import pypff; print('pypff installed:', pypff.__version__ if hasattr(pypff, '__version__') else 'ok')"

echo "[*] cleaning up..."
rm -rf "$WORKDIR"

echo "[+] done. pypff is ready for dotty email analysis."

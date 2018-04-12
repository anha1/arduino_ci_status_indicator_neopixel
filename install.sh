#!/bin/sh
set -e
dir=/usr/local/ci-status-neopixel
if [ "$PWD" != "$dir" ]; then
	echo "Please run from '$dir'!";
	exit 1;
fi
cp -n ./systemd/ci-midori.service /usr/lib/systemd/system/ci-midori.service
cp -n ./systemd/ci-status-neopixel.service /usr/lib/systemd/system/ci-status-neopixel.service
cp -n ./service/settings.ini /etc/ci-status-neopixel/settings.ini
systemctl daemon-reload
systemctl enable ci-status-neopixel
systemctl enable ci-midori
systemctl start ci-status-neopixel
systemctl start ci-midori
echo "done!"

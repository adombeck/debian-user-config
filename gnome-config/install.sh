#!/bin/sh

dconf load /org/gnome/ < gnome.dconf

# Enable udisks TCRYPT support
sudo touch /etc/udisks2/tcrypt.conf


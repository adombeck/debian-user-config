#!/bin/sh

screenlock-watcher.sh &

if zenity --question --text "Run startup applications?"; then
	keepassxc &
	pidgin &
	thunderbird &
	firefox &
	nextcloud &
	gtk-launch com.spotify.Client.desktop &
fi


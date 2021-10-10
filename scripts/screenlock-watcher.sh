exit_report(){
	echo "$(date) Monitoring Terminated."
}
trap "exit_report; exit;" 0


adddate() {
	while IFS= read -r line; do
		echo "$(date) $line"
	done
}

lockmon() {
echo "$(date) Monitoring Started."

dbus-monitor --session "type='signal',interface='org.gnome.ScreenSaver',member='ActiveChanged'" | adddate | grep --line-buffered boolean | sed -u 's/\s*boolean true/ Screen locked/' | sed -u 's/\s*boolean false/ Screen unlocked/' &

dbus-monitor --system "type='signal',sender='org.freedesktop.login1',interface='org.freedesktop.login1.Manager',member='PrepareForSleep'"| adddate | grep --line-buffered boolean | sed -u 's/\s*boolean true/ Suspending/' | sed -u 's/\s*boolean false/ Waking from suspend/' &
}

lockmon >> ~/lock_screen.log

#!/usr/bin/env python3

import sys

from gi.repository import Gio, GLib

media_keys_schema = "org.gnome.settings-daemon.plugins.media-keys"
custom_keybinding_schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
keybinding_path_prefix = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

usage_message = '''Usage: {cmd} <name> <command> <binding>

Example:
{cmd} "Open gedit" "gedit" "<Shift><Ctrl>G"
'''.format(cmd=sys.argv[0])


def main():
    if len(sys.argv) < 4:
        sys.exit(usage_message)
    name = sys.argv[1]
    command = sys.argv[2]
    binding = sys.argv[3]

    settings = Gio.Settings(schema=media_keys_schema)
    binding_paths = settings.get_value("custom-keybindings").unpack()  # type: list[str]

    # Figure out which path to use for the new binding. If a binding
    # of the same name already exists, we replace it.
    path = find(binding_paths, name)
    if not path:
        # Use the first gsettings path that doesn't exist yet
        n = 0
        path = keybinding_path_prefix + f"custom{n}/"
        while path in binding_paths:
            n += 1
            path = keybinding_path_prefix + f"custom{n}/"

    # Create the new keybinding
    setting = Gio.Settings(schema=custom_keybinding_schema, path=path)
    setting.set_string("name", name)
    setting.set_string("command", command)
    setting.set_string("binding", binding)
    setting.sync()

    if path not in binding_paths:
        # Add the new keybinding to the list of custom keybindings
        binding_paths.append(path)
        settings.set_value("custom-keybindings", GLib.Variant("as", binding_paths))
        setting.sync()


def find(binding_paths: list[str], name: str) -> str:
    for path in binding_paths:
        setting = Gio.Settings(schema=custom_keybinding_schema, path=path)
        setting_name = setting.get_value("name").unpack()
        if setting_name == name:
            return path


if __name__ == "__main__":
    main()

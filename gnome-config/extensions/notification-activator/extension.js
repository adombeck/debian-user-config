import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const ACTIVATE_NOTIFICATION = 'activate-notification';

export default class NotificationActivatorExtension extends Extension {
    #lastNotification = null;
    #queueChangedId = 0;

    enable() {
        this.#queueChangedId = Main.messageTray.connect('queue-changed', () => {
            const notification = Main.messageTray._notification;
            if (notification && !notification._destroyed)
                this.#lastNotification = notification;
        });

        Main.wm.addKeybinding(
            ACTIVATE_NOTIFICATION,
            this.getSettings(),
            Meta.KeyBindingFlags.IGNORE_AUTOREPEAT,
            Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW,
            () => this.#activateNotification(),
        );
    }

    disable() {
        Main.wm.removeKeybinding(ACTIVATE_NOTIFICATION);

        if (this.#queueChangedId)
            Main.messageTray.disconnect(this.#queueChangedId);
        this.#queueChangedId = 0;
        this.#lastNotification = null;
    }

    #activateNotification() {
        const notification = Main.messageTray._notification ?? this.#lastNotification;
        if (!notification || notification._destroyed)
            return;

        notification.activate();
    }
}

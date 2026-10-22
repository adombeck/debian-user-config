# Mattermost session notifications

Run `copilot/install.sh` from this repository to install the extension.
It uses the SDK bundled with Copilot CLI and needs Node.js 22 or later.

Store the incoming webhook in `~/.copilot/session-notify/webhook.json`:

```json
{"webhook":"https://mattermost.example/hooks/REPLACE_ME"}
```

Keep this file outside Git. Set its mode to `600` and its parent directory's
mode to `700`.

In an already-running Copilot session, ask Copilot to reload extensions from
disk. Then use:

```text
/notify on my-task
/notify status
/notify test
/notify off
```

Notifications are off by default. Each session keeps its own setting and label
in `~/.copilot/session-notify/sessions/`, including across reloads and resumes.
Labels can contain 1-64 letters, numbers, spaces, dots, hyphens, or underscores.
Enabling notifications also sends a confirmation to Mattermost.

Messages contain only the label and status, not code, prompts, questions, or
responses. Notifications report idle turns, interrupted turns, questions,
permissions, forms, plan approval, and session limits. Idle means the turn
finished, not that the task succeeded. Input requests resolved within 1.5
seconds do not trigger a notification. Delivery failures appear in the local
session; they are not retried automatically.

Run the tests with:

```sh
node --test copilot/extensions/session-notify/notifier.test.mjs
```

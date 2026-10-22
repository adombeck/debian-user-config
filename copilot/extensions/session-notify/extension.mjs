import { mkdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { joinSession } from "@github/copilot-sdk/extension";
import { createNotifier, postMattermost } from "./notifier.mjs";

// Keep secrets and session state outside the symlinked extension source.
const configDirectory = join(homedir(), ".copilot", "session-notify");
const directory = join(configDirectory, "sessions");
await mkdir(directory, { recursive: true, mode: 0o700 });

let notifier;
const session = await joinSession({
    commands: [{
        name: "notify",
        description: "Mattermost notifications: on [label], off, status, test",
        handler: async ({ args }) => notifier.command(args),
    }],
});

if (!/^[a-zA-Z0-9-]+$/.test(session.sessionId)) {
    throw new Error("Cannot store notification settings: invalid session ID.");
}
const statePath = join(directory, `${session.sessionId}.json`);
let state = { enabled: false, label: session.sessionId.slice(0, 8) };
try {
    state = JSON.parse(await readFile(statePath, "utf8"));
} catch (error) {
    if (error.code !== "ENOENT") {
        throw new Error("Cannot read session notification settings.");
    }
}

notifier = createNotifier({
    session,
    state,
    save: async (next) => {
        await writeFile(statePath, JSON.stringify(next) + "\n", { mode: 0o600 });
    },
    send: async (text) => {
        let config;
        try {
            config = JSON.parse(await readFile(join(configDirectory, "webhook.json"), "utf8"));
        } catch {
            throw new Error("Cannot read ~/.copilot/session-notify/webhook.json.");
        }
        await postMattermost(config.webhook, text);
    },
});
session.on((event) => notifier.event(event));

// Extension: guake-notify
// Rich desktop notifications when the agent is idle (waiting for input).
// Sends a desktop notification showing the session name and an action button
// that switches to the guake tab where the session is running.

import { joinSession } from "@github/copilot-sdk/extension";
import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

/** Return the currently selected guake tab index, or null if unavailable. */
async function getGuakeTabIndex() {
    try {
        const { stdout } = await execFileAsync("guake", ["-g"]);
        const index = stdout.trim();
        return index !== "" ? index : null;
    } catch {
        return null;
    }
}

let guakeTabIndex = null;

/** Send a desktop notification with an optional "Switch to tab" action button. */
function sendNotification(title, tabIndex) {
    const notifyArgs = ["--app-name=Copilot CLI", "--icon=github", "--transient"];

    if (tabIndex !== null) {
        // --action implies --wait; use a detached shell so we don't block.
        notifyArgs.push("--action=Switch to tab");
    }

    notifyArgs.push("Copilot CLI", title);

    const switchCmd = tabIndex !== null ? `guake --show; guake -s ${tabIndex}` : "";

    // prettier-ignore
    const shellScript = tabIndex !== null
        ? `action=$(notify-send ${notifyArgs.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(" ")}); [ "$action" = "0" ] && { ${switchCmd}; } || true`
        : `notify-send ${notifyArgs.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(" ")}`;

    const child = spawn("bash", ["-c", shellScript], {
        detached: true,
        stdio: "ignore",
    });
    child.unref();
}

const session = await joinSession({
    tools: [],
    hooks: {
        onSessionStart: async (_input, _invocation) => {
            guakeTabIndex = await getGuakeTabIndex();
        },
    },
});

// Track whether we've seen at least one user message so we don't notify on the
// initial idle state that fires before the user has sent anything.
let hasUserMessage = false;
session.on("user.message", () => {
    hasUserMessage = true;
});

session.on("session.idle", async (event) => {
    if (!hasUserMessage || event.data?.aborted) return;

    let sessionName = null;
    try {
        const result = await session.rpc.name.get();
        if (result?.name) sessionName = result.name;
    } catch {
        // ignore — RPC may not be available
    }
    const title = sessionName ?? "Copilot CLI";

    sendNotification(title, guakeTabIndex);
});

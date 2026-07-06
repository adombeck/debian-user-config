// Extension: guake-notify
// Rich desktop notifications for session completion with guake tab switching.
// When the agent finishes, sends a desktop notification showing the session
// name and an action button that switches to the guake tab where the session
// is running.

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

const session = await joinSession({
    tools: [],
    hooks: {
        onSessionStart: async (_input, _invocation) => {
            guakeTabIndex = await getGuakeTabIndex();
        },

        onSessionEnd: async (_input, invocation) => {
            // Resolve the session name; fall back to the session ID prefix.
            let sessionName = null;
            try {
                const result = await session.rpc.name.get();
                if (result?.name) sessionName = result.name;
            } catch {
                // ignore — RPC may not be available during shutdown
            }
            const title = sessionName ?? `Session ${invocation.sessionId.slice(0, 8)}`;

            // Build the notify-send command. Using --action implies --wait, so we
            // detach a helper shell process to avoid blocking the shutdown path.
            const tabIndex = guakeTabIndex;
            const notifyArgs = ["--app-name=Copilot CLI", "--icon=github"];

            if (tabIndex !== null) {
                // Add an action button; the action name "0" is printed to stdout
                // when the user clicks it.
                notifyArgs.push("--action=Switch to tab");
            }

            notifyArgs.push("Copilot CLI", title);

            // Inline shell script so the detached process is fully self-contained.
            const switchCmd = tabIndex !== null
                ? `guake --show; guake -s ${tabIndex}`
                : "";

            // prettier-ignore
            const shellScript = tabIndex !== null
                ? `action=$(notify-send ${notifyArgs.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(" ")}); [ "$action" = "0" ] && { ${switchCmd}; } || true`
                : `notify-send ${notifyArgs.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(" ")}`;

            const child = spawn("bash", ["-c", shellScript], {
                detached: true,
                stdio: "ignore",
            });
            child.unref();
        },
    },
});

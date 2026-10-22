const labelPattern = /^[a-zA-Z0-9 _.-]{1,64}$/;
const waitingEvents = new Map([
    ["permission.requested", "needs your permission"],
    ["user_input.requested", "needs your input"],
    ["elicitation.requested", "needs your input"],
    ["exit_plan_mode.requested", "needs your plan approval"],
    ["session_limits_exhausted.requested", "needs your input about a session limit"],
]);

export async function postMattermost(webhook, text, fetchImpl = fetch) {
    let url;
    try {
        url = new URL(webhook);
    } catch {
        throw new Error("Invalid Mattermost webhook URL.");
    }
    if (url.protocol !== "https:" || url.username || url.password) {
        throw new Error("The Mattermost webhook must use HTTPS without URL credentials.");
    }
    let response;
    try {
        response = await fetchImpl(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
            redirect: "error",
            signal: AbortSignal.timeout(10_000),
        });
    } catch {
        // Fetch errors can contain the secret webhook URL.
        throw new Error("Mattermost delivery failed: network error or timeout.");
    }
    if (!response.ok) {
        throw new Error(`Mattermost delivery failed: HTTP ${response.status}.`);
    }
    await response.body?.cancel();
}

export function createNotifier({ session, state, save, send, delay = 1500 }) {
    if (typeof state.enabled !== "boolean" || !labelPattern.test(state.label)) {
        throw new Error("Invalid session notification settings.");
    }
    state = { ...state };
    let idleNotified = false;
    let queue = Promise.resolve();
    const pending = new Map();

    function clearPending() {
        for (const timer of pending.values()) clearTimeout(timer);
        pending.clear();
    }

    function notify(status) {
        const label = state.label;
        queue = queue.then(async () => {
            if (state.enabled) await send(`Copilot [${label}]: ${status}.`);
        }).catch(async (error) => {
            try {
                await session.log(error.message, { level: "error" });
            } catch {
                console.error("session-notify: delivery failed; cannot log to the session.");
            }
        });
    }

    return {
        async command(args) {
            const [action = "status", ...words] = args.trim().split(/\s+/).filter(Boolean);
            if (action === "on") {
                const label = words.join(" ") || state.label;
                if (!labelPattern.test(label)) {
                    await session.log("Use a label of 1-64 letters, numbers, spaces, dots, hyphens, or underscores.", { level: "error" });
                    return;
                }
                await send(`Copilot [${label}]: notifications enabled.`);
                const next = { enabled: true, label };
                await save(next);
                state = next;
                idleNotified = false;
                await session.log(`Mattermost notifications ON for ${label}. Only the label and status are sent.`);
            } else if (action === "off" && words.length === 0) {
                const next = { ...state, enabled: false };
                await save(next);
                state = next;
                clearPending();
                await session.log("Mattermost notifications OFF for this session.");
            } else if (action === "test" && words.length === 0) {
                await send(`Copilot [${state.label}]: test notification.`);
                await session.log("Mattermost test notification sent.");
            } else if (action === "status" && words.length === 0) {
                await session.log(`Mattermost notifications ${state.enabled ? "ON" : "OFF"} for ${state.label}.`);
            } else {
                await session.log("Usage: /notify on [label] | off | status | test", { level: "error" });
            }
        },
        event(event) {
            if (!state.enabled) return;
            if (!event.agentId && (event.type === "assistant.turn_start" || event.type === "user.message")) {
                idleNotified = false;
            }
            if (event.type.endsWith(".completed")) {
                const key = `${event.type.replace(/\.completed$/, "")}:${event.data.requestId}`;
                clearTimeout(pending.get(key));
                pending.delete(key);
            }
            const waiting = waitingEvents.get(event.type);
            if (waiting && !event.data.resolvedByHook) {
                const key = `${event.type.replace(/\.requested$/, "")}:${event.data.requestId}`;
                if (pending.has(key)) return;
                pending.set(key, setTimeout(() => {
                    // Keep the entry until completion so repeated requests do not notify twice.
                    pending.set(key, undefined);
                    notify(waiting);
                }, delay));
            }
            if (event.type === "session.idle" && !event.agentId && !idleNotified) {
                idleNotified = true;
                clearPending();
                notify(event.data.aborted ? "was interrupted and is now idle" : "is idle (turn finished)");
            }
        },
        settled: () => queue,
        dispose: clearPending,
    };
}

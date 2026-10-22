import { test } from "node:test";
import assert from "node:assert/strict";
import { createNotifier, postMattermost } from "./notifier.mjs";

function fixture(t, options = {}) {
    const sent = [];
    const logs = [];
    const saved = [];
    const notifier = createNotifier({
        session: { log: async (message) => logs.push(message) },
        state: { enabled: false, label: "test-session" },
        save: async (state) => saved.push(state),
        send: async (text) => sent.push(text),
        delay: 1500,
        ...options,
    });
    t.after(() => notifier.dispose());
    return { notifier, sent, logs, saved };
}

const event = (type, data = {}, extra = {}) => ({ type, data, ...extra });

test("sessions are opt-in; enabling, disabling, and labels persist", async (t) => {
    const { notifier, sent, saved } = fixture(t);
    notifier.event(event("session.idle"));
    await notifier.settled();
    assert.equal(sent.length, 0);
    await notifier.command("on work-1");
    assert.deepEqual(saved[0], { enabled: true, label: "work-1" });
    notifier.event(event("session.idle"));
    await notifier.settled();
    assert.equal(sent[1], "Copilot [work-1]: is idle (turn finished).");
    await notifier.command("off");
    notifier.event(event("session.idle"));
    await notifier.settled();
    assert.equal(sent.length, 2);
    assert.deepEqual(saved[1], { enabled: false, label: "work-1" });
});

test("idle is deduplicated, ignores child idle, and distinguishes cancellation", async (t) => {
    const { notifier, sent } = fixture(t, { state: { enabled: true, label: "work" } });
    notifier.event(event("session.idle", {}, { agentId: "child" }));
    notifier.event(event("session.idle"));
    notifier.event(event("session.idle"));
    await notifier.settled();
    assert.equal(sent.length, 1);
    notifier.event(event("assistant.turn_start"));
    notifier.event(event("session.idle", { aborted: true }));
    await notifier.settled();
    assert.equal(sent[1], "Copilot [work]: was interrupted and is now idle.");
});

test("questions, forms, permissions, plan approval, and limits send no content", async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const { notifier, sent } = fixture(t, { state: { enabled: true, label: "work" } });
    for (const type of [
        "user_input.requested", "elicitation.requested", "permission.requested",
        "exit_plan_mode.requested", "session_limits_exhausted.requested",
    ]) {
        const request = event(type, { requestId: type, question: "SECRET", permissionRequest: { command: "SECRET" } });
        notifier.event(request);
        notifier.event(request);
    }
    t.mock.timers.tick(1500);
    await notifier.settled();
    assert.equal(sent.length, 5);
    assert.ok(sent.every((text) => !text.includes("SECRET")));
    notifier.event(event("permission.requested", { requestId: "permission.requested" }));
    t.mock.timers.tick(1500);
    await notifier.settled();
    assert.equal(sent.length, 5);
});

test("quickly resolved prompts and hook-approved permissions do not notify", async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const { notifier, sent } = fixture(t, { state: { enabled: true, label: "work" } });
    notifier.event(event("permission.requested", { requestId: "auto" }));
    notifier.event(event("permission.completed", { requestId: "auto" }));
    notifier.event(event("permission.requested", { requestId: "hook", resolvedByHook: true }));
    notifier.event(event("user_input.requested", { requestId: "quick" }));
    notifier.event(event("user_input.completed", { requestId: "quick" }));
    t.mock.timers.tick(1500);
    await notifier.settled();
    assert.equal(sent.length, 0);
});

test("disabling cancels pending notifications", async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const { notifier, sent } = fixture(t, { state: { enabled: true, label: "work" } });
    notifier.event(event("user_input.requested", { requestId: "pending" }));
    await notifier.command("off");
    t.mock.timers.tick(1500);
    await notifier.settled();
    assert.equal(sent.length, 0);
});

test("delivery failures are visible and do not break later notifications", async (t) => {
    let calls = 0;
    const { notifier, logs } = fixture(t, {
        state: { enabled: true, label: "work" },
        send: async () => {
            if (++calls === 1) throw new Error("Mattermost delivery failed: HTTP 500.");
        },
    });
    notifier.event(event("session.idle"));
    await notifier.settled();
    assert.match(logs[0], /HTTP 500/);
    notifier.event(event("assistant.turn_start"));
    notifier.event(event("session.idle"));
    await notifier.settled();
    assert.equal(calls, 2);
});

test("failed enable does not persist an enabled state", async (t) => {
    const { notifier, saved } = fixture(t, {
        send: async () => { throw new Error("delivery failed"); },
    });
    await assert.rejects(notifier.command("on"), /delivery failed/);
    assert.equal(saved.length, 0);
});

test("labels cannot inject mentions, Markdown, or newlines", async (t) => {
    const { notifier, sent, logs } = fixture(t);
    await notifier.command("on @channel");
    assert.equal(sent.length, 0);
    assert.match(logs[0], /Use a label/);
});

test("webhook requests are HTTPS, bounded, and never follow redirects", async () => {
    let cancelled = false;
    await postMattermost("https://example.invalid/hooks/secret", "Generic status", async (url, options) => {
        assert.equal(url.protocol, "https:");
        assert.equal(options.method, "POST");
        assert.equal(options.redirect, "error");
        assert.ok(options.signal instanceof AbortSignal);
        assert.deepEqual(JSON.parse(options.body), { text: "Generic status" });
        return { ok: true, body: { cancel: async () => { cancelled = true; } } };
    });
    assert.ok(cancelled);
    await assert.rejects(postMattermost("http://example.invalid/hooks/secret", "test"), /HTTPS/);
});

test("webhook errors do not reveal secrets and non-2xx is a failure", async () => {
    await assert.rejects(
        postMattermost("https://example.invalid/hooks/secret", "test", async () => {
            throw new Error("Failed to fetch https://example.invalid/hooks/secret");
        }),
        (error) => !error.message.includes("secret") && /network/.test(error.message),
    );
    await assert.rejects(
        postMattermost("https://example.invalid/hooks/secret", "test", async () => ({ ok: false, status: 403 })),
        /HTTP 403/,
    );
});

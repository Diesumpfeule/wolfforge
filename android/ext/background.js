// Hands every page its CSS. Runs only when needed (an event page), so settings are read from storage
// once per wake-up and again whenever they change.
"use strict";

let ready = null;

function state() {
  if (!ready) ready = Promise.all([WF.load(), WF.data()]).then(([cfg, data]) => ({ cfg, data }));
  return ready;
}

browser.storage.onChanged.addListener(() => { ready = null; });

browser.runtime.onMessage.addListener((msg, sender) => {
  if (!msg || msg.t !== "css" || !sender.tab) return undefined;
  return state().then(({ cfg, data }) => {
    let host = "";
    try { host = new URL(sender.url).hostname; } catch (e) { return false; }
    const code = WF.cssFor(cfg, data, host, msg.dark);
    if (!code) return false;
    // insertCSS as a user style sheet: works on pages whose own rules forbid injected <style> tags
    return browser.tabs.insertCSS(sender.tab.id, { code, frameId: sender.frameId, runAt: "document_start", cssOrigin: "user" })
      .then(() => true, () => false);
  });
});

browser.runtime.onInstalled.addListener(details => {
  if (details.reason === "install") browser.runtime.openOptionsPage();
});

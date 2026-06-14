# Garuda VPN - Browser Addon (Educational POC Payload)

**Garuda VPN** is a simulated "VPN service" browser extension that acts as a stealthy agent for the B.E.G.A.L C2 Framework. It is designed to demonstrate how a rogue extension can compromise a user's browser, harvest sensitive data, and execute remote commands under the guise of a utility tool.

<img width="426" height="628" alt="Screenshot From 2026-06-14 22-44-36" src="https://github.com/user-attachments/assets/376bc901-7ac1-4949-a282-38c46ba3b4bc" />

---

## ⚠️ LEGAL DISCLAIMER

**THIS PROJECT IS FOR EDUCATIONAL AND ETHICAL SECURITY RESEARCH ONLY.**

Installing this extension on any browser without the owner's explicit and written consent is a crime. Use this code only in a controlled laboratory environment to understand browser-based threats and develop better defensive measures. Unauthorized use may violate the **Indonesian ITE Law**, the **CFAA (USA)**, and other international cybercrime regulations.

---

## 🛠️ Main Features (Agent Capabilities)

When installed and connected to the B.E.G.A.L C2 server, this addon performs the following functions:

1.  **Stealth Credential Harvesting**: Automatically intercepts HTML form submissions to steal usernames and passwords from login pages.
2.  **Keylogging**: Silently records keystrokes and periodically sends them to the C2 server.
3.  **Cookie & Session Stealing**: Can extract all active browser cookies to hijack authenticated user sessions.
4.  **Clipboard Hijacking**: Captures data whenever the target user performs a "Paste" action.
5.  **Remote Multimedia Access**:
    *   **Webcam Capture**: Remotely triggers the target's camera and exfiltrates images.
    *   **Microphone Recording**: Records audio clips from the target's surroundings.
6.  **Screen Capture**: Takes instant screenshots of the active browser tab.
7.  **Service Worker Persistence**: Uses Manifest V3 heartbeat mechanisms to ensure the "agent" stays alive in the background even during inactivity.

---

## 📁 File Structure

*   **`manifest.json`**: Defines extension metadata, permissions (tabs, cookies, storage), and background service worker.
*   **`background.js`**: The core logic handler. Responsible for data exfiltration, XOR encryption, and polling the C2 for remote commands.
*   **`content.js`**: The payload script injected into every webpage. Handles keylogging, form interception, and access to hardware (Webcam/Mic).
*   **`popup.html/js`**: The fake UI presented to the user, disguised as a high-end VPN control panel to avoid suspicion.

---

## 🚀 Installation & Integration

### 1. Prerequisite: C2 Server
Ensure your B.E.G.A.L C2 server is running (`begal-fixed.py`) on `http://127.0.0.1:31337`.

### 2. Matching Encryption Keys
Open `background.js` and verify that the `XOR_KEY` matches the one set in your C2 `config.yaml`:
```javascript
const XOR_KEY = "FLIPPER_SECURE_XOR_KEY_1337"; // Must match C2
```

### 3. Installation on Browser
1.  Open Google Chrome or any Chromium-based browser (Edge, Brave).
2.  Navigate to `chrome://extensions`.
3.  Toggle the **"Developer mode"** switch in the top right corner.
4.  Click the **"Load unpacked"** button.
5.  Select the `garuda-vpn` folder from this repository.

### 4. Deployment
*   Once installed, the "Garuda VPN" icon will appear in the toolbar.
*   The extension will automatically generate a unique `botUUID` for the target machine.
*   Check your B.E.G.A.L Dashboard; the browser should now appear in the **"Active Bots"** list.

### 5. Stealth
*   To make Garuda-VPN better, don't forget to obfuscate each .js file.

---

## 🔒 Security Measures
All communications between this addon and the C2 server are protected via a **symmetric XOR encryption** layer. This disguises the JSON data as random Base64 strings, making it harder for basic Network IDS or "Inspect Element" network logs to flag the exfiltrated content immediately.

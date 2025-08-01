// 배치 클립 생성 페이지 스크립트

let batchJobId = null;
let batchStatusInterval = null;
let batchClipCount = 0;

// 배치 클립 생성
async function createBatchClips() {
    const clips = [];
    document.querySelectorAll('.clip-entry').forEach((entry, index) => {
        const clip = {
            start_time: parseFloat(entry.querySelector('.clip-start-time').value),
            end_time: parseFloat(entry.querySelector('.clip-end-time').value),
            text_eng: entry.querySelector('.clip-text-eng').value,
            text_kor: entry.querySelector('.clip-text-kor').value,
            note: entry.querySelector('.clip-note').value,
            keywords: entry.querySelector('.clip-keywords').value.split(',').map(k => k.trim()).filter(k => k)
        };
        clips.push(clip);
    });

    const data = {
        media_path: document.getElementById('batch-media-path').value,
        clips: clips,
        clipping_type: parseInt(document.getElementById('batch-clipping-type').value),
        individual_clips: document.getElementById('batch-individual-clips').checked
    };

    try {
        const response = await fetch(`${API_BASE_URL}/api/clip/batch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Batch creation failed');
        }

        const result = await response.json();
        batchJobId = result.job_id;
        
        // 상태 표시
        document.getElementById('batch-job-status').classList.remove('hidden');
        document.getElementById('batch-job-id').textContent = `Job ID: ${batchJobId}`;
        
        // 배치 상태 체크 시작
        startBatchStatusCheck();
        
    } catch (error) {
        showError(error.message);
    }
}

// 클립 엔트리 추가
function addClipEntry() {
    batchClipCount++;
    const clipEntry = document.createElement('div');
    clipEntry.className = 'clip-entry';
    clipEntry.innerHTML = `
        <div class="clip-entry-header">
            <span class="clip-number">클립 ${batchClipCount}</span>
            <button class="remove-clip-btn" onclick="removeClipEntry(this)">삭제</button>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>시작 시간 (초)</label>
                <input type="number" class="clip-start-time" step="0.1" min="0" required>
            </div>
            <div class="form-group">
                <label>종료 시간 (초)</label>
                <input type="number" class="clip-end-time" step="0.1" min="0" required>
            </div>
        </div>
        <div class="form-group">
            <label>영문 자막</label>
            <textarea class="clip-text-eng" rows="2" required></textarea>
        </div>
        <div class="form-group">
            <label>한국어 번역</label>
            <textarea class="clip-text-kor" rows="2" required></textarea>
        </div>
        <div class="form-group">
            <label>문장 설명</label>
            <textarea class="clip-note" rows="1"></textarea>
        </div>
        <div class="form-group">
            <label>키워드 (쉼표로 구분)</label>
            <input type="text" class="clip-keywords">
        </div>
    `;
    
    const clipsList = document.getElementById('clips-list');
    if (clipsList) {
        clipsList.appendChild(clipEntry);
    }
}

// 클립 엔트리 제거
function removeClipEntry(button) {
    if (document.querySelectorAll('.clip-entry').length > 1) {
        button.closest('.clip-entry').remove();
        updateClipNumbers();
    }
}

// 클립 번호 업데이트
function updateClipNumbers() {
    document.querySelectorAll('.clip-entry').forEach((entry, index) => {
        entry.querySelector('.clip-number').textContent = `클립 ${index + 1}`;
    });
    batchClipCount = document.querySelectorAll('.clip-entry').length;
}

// 배치 상태 체크 시작
function startBatchStatusCheck() {
    batchStatusInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/batch/status/${batchJobId}`);
            if (response.ok) {
                const status = await response.json();
                updateBatchStatus(status);
                
                if (status.status === 'completed' || status.status === 'failed') {
                    clearInterval(batchStatusInterval);
                    if (status.status === 'completed') {
                        showSuccess('배치 클립 생성이 완료되었습니다!');
                    }
                }
            }
        } catch (error) {
            console.error('Batch status check error:', error);
        }
    }, 1000);
}

// 배치 상태 업데이트
function updateBatchStatus(status) {
    // 상태 배지 업데이트
    const badge = document.getElementById('batch-status-badge');
    badge.className = `status-badge ${status.status}`;
    badge.textContent = getStatusText(status.status);
    
    // 진행률 업데이트
    document.getElementById('batch-progress-bar').style.width = `${status.progress}%`;
    
    // 메시지 업데이트
    document.getElementById('batch-status-message').textContent = status.message;
    
    // 결과 표시
    if (status.status === 'completed' && status.output_files) {
        displayBatchResults(status.output_files);
    }
}

// 배치 결과 표시
function displayBatchResults(files) {
    const resultsDiv = document.getElementById('batch-results');
    resultsDiv.innerHTML = '<h4>완료된 클립:</h4>';
    
    files.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'batch-item';
        item.innerHTML = `
            <span>클립 ${index + 1}: ${file.start_time}s - ${file.end_time}s</span>
            <button class="download-btn" onclick="downloadBatchClip('${batchJobId}', ${file.clip_num})">
                다운로드
            </button>
        `;
        resultsDiv.appendChild(item);
    });
}

// 배치 클립 다운로드
function downloadBatchClip(jobId, clipNum) {
    window.open(`${API_BASE_URL}/api/batch/download/${jobId}/${clipNum}`, '_blank');
}

// 배치 클립 초기화
function initBatchClips() {
    if (document.getElementById('clips-list') && document.querySelectorAll('.clip-entry').length === 0) {
        addClipEntry();
    }
}
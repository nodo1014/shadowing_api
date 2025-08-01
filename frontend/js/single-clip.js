// 단일 클립 생성 페이지 스크립트

let currentJobId = null;
let statusCheckInterval = null;

// 단일 클립 생성
async function createSingleClip() {
    const data = {
        media_path: document.getElementById('media-path').value,
        start_time: parseFloat(document.getElementById('start-time').value),
        end_time: parseFloat(document.getElementById('end-time').value),
        text_eng: document.getElementById('text-eng').value,
        text_kor: document.getElementById('text-kor').value,
        note: document.getElementById('note').value,
        keywords: document.getElementById('keywords').value.split(',').map(k => k.trim()).filter(k => k),
        clipping_type: parseInt(document.getElementById('clipping-type').value),
        individual_clips: document.getElementById('individual-clips').checked
    };

    try {
        const response = await fetch(`${API_BASE_URL}/api/clip`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Clip creation failed');
        }

        const result = await response.json();
        currentJobId = result.job_id;
        
        // 상태 표시
        document.getElementById('job-status').classList.remove('hidden');
        document.getElementById('current-job-id').textContent = `Job ID: ${currentJobId}`;
        
        // 상태 체크 시작
        startStatusCheck();
        
    } catch (error) {
        showError(error.message);
    }
}

// 상태 체크 시작
function startStatusCheck() {
    statusCheckInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/status/${currentJobId}`);
            if (response.ok) {
                const status = await response.json();
                updateJobStatus(status);
                
                if (status.status === 'completed' || status.status === 'failed') {
                    clearInterval(statusCheckInterval);
                    if (status.status === 'completed') {
                        showSuccess('클립 생성이 완료되었습니다!');
                    }
                }
            }
        } catch (error) {
            console.error('Status check error:', error);
        }
    }, 1000);
}

// 작업 상태 업데이트
function updateJobStatus(status) {
    // 상태 배지 업데이트
    const badge = document.getElementById('status-badge');
    badge.className = `status-badge ${status.status}`;
    badge.textContent = getStatusText(status.status);
    
    // 진행률 업데이트
    document.getElementById('progress-bar').style.width = `${status.progress}%`;
    
    // 메시지 업데이트
    document.getElementById('status-message').textContent = status.message;
    
    // 완료 시 다운로드 버튼 표시
    if (status.status === 'completed' && status.output_file) {
        document.getElementById('download-btn').classList.remove('hidden');
    }
}

// 클립 다운로드
function downloadClip() {
    if (currentJobId) {
        window.open(`${API_BASE_URL}/api/download/${currentJobId}`, '_blank');
    }
}

// 작업 취소
function cancelJob() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    document.getElementById('job-status').classList.add('hidden');
    currentJobId = null;
}
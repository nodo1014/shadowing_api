// API Base URL
const API_BASE_URL = 'http://localhost:8080';

// 전역 변수
let currentJobId = null;
let statusCheckInterval = null;
let batchClipCount = 0;

// DOM 로드 완료 시
document.addEventListener('DOMContentLoaded', () => {
    // 모드 선택 버튼 이벤트
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            switchMode(e.target.dataset.mode);
        });
    });

    // 최근 작업 목록 로드
    loadRecentJobs();
});

// 모드 전환
function switchMode(mode) {
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-mode="${mode}"]`).classList.add('active');

    document.querySelectorAll('.clip-form').forEach(form => {
        form.classList.remove('active');
    });

    if (mode === 'single') {
        document.getElementById('single-clip-form').classList.add('active');
    } else {
        document.getElementById('batch-clip-form').classList.add('active');
        if (batchClipCount === 0) {
            addClipEntry();
        }
    }
}

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

    // 유효성 검사
    if (!data.media_path || !data.start_time || !data.end_time || !data.text_eng || !data.text_kor) {
        alert('필수 필드를 모두 입력해주세요.');
        return;
    }

    if (data.start_time >= data.end_time) {
        alert('종료 시간은 시작 시간보다 커야 합니다.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/clip`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            const result = await response.json();
            currentJobId = result.job_id;
            showJobStatus(result.job_id);
            startStatusCheck();
            clearSingleClipForm();
        } else {
            const error = await response.json();
            alert(`오류: ${error.detail}`);
        }
    } catch (error) {
        alert(`요청 실패: ${error.message}`);
    }
}

// 배치 클립 엔트리 추가
function addClipEntry() {
    batchClipCount++;
    const clipsList = document.getElementById('clips-list');
    
    const clipEntry = document.createElement('div');
    clipEntry.className = 'clip-entry';
    clipEntry.dataset.clipNumber = batchClipCount;
    
    clipEntry.innerHTML = `
        <div class="clip-entry-header">
            <span class="clip-number">클립 ${batchClipCount}</span>
            <button class="remove-clip-btn" onclick="removeClipEntry(${batchClipCount})">삭제</button>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>시작 시간 (초) *</label>
                <input type="number" class="batch-start-time" step="0.1" min="0" required>
            </div>
            <div class="form-group">
                <label>종료 시간 (초) *</label>
                <input type="number" class="batch-end-time" step="0.1" min="0" required>
            </div>
        </div>
        <div class="form-group">
            <label>영문 자막 *</label>
            <textarea class="batch-text-eng" rows="2" required></textarea>
        </div>
        <div class="form-group">
            <label>한국어 번역 *</label>
            <textarea class="batch-text-kor" rows="2" required></textarea>
        </div>
        <div class="form-group">
            <label>문장 설명</label>
            <textarea class="batch-note" rows="2"></textarea>
        </div>
        <div class="form-group">
            <label>키워드 (쉼표로 구분)</label>
            <input type="text" class="batch-keywords">
        </div>
    `;
    
    clipsList.appendChild(clipEntry);
}

// 배치 클립 엔트리 제거
function removeClipEntry(clipNumber) {
    const clipEntry = document.querySelector(`[data-clip-number="${clipNumber}"]`);
    if (clipEntry) {
        clipEntry.remove();
    }
}

// 배치 클립 생성
async function createBatchClips() {
    const mediaPath = document.getElementById('batch-media-path').value;
    const clippingType = parseInt(document.getElementById('batch-clipping-type').value);
    const individualClips = document.getElementById('batch-individual-clips').checked;
    
    if (!mediaPath) {
        alert('미디어 파일 경로를 입력해주세요.');
        return;
    }
    
    const clips = [];
    const clipEntries = document.querySelectorAll('.clip-entry');
    
    for (const entry of clipEntries) {
        const startTime = parseFloat(entry.querySelector('.batch-start-time').value);
        const endTime = parseFloat(entry.querySelector('.batch-end-time').value);
        const textEng = entry.querySelector('.batch-text-eng').value;
        const textKor = entry.querySelector('.batch-text-kor').value;
        const note = entry.querySelector('.batch-note').value;
        const keywords = entry.querySelector('.batch-keywords').value.split(',').map(k => k.trim()).filter(k => k);
        
        if (!startTime || !endTime || !textEng || !textKor) {
            alert('모든 클립의 필수 필드를 입력해주세요.');
            return;
        }
        
        if (startTime >= endTime) {
            alert('종료 시간은 시작 시간보다 커야 합니다.');
            return;
        }
        
        clips.push({
            start_time: startTime,
            end_time: endTime,
            text_eng: textEng,
            text_kor: textKor,
            note: note,
            keywords: keywords
        });
    }
    
    if (clips.length === 0) {
        alert('최소 하나 이상의 클립을 추가해주세요.');
        return;
    }
    
    const data = {
        media_path: mediaPath,
        clips: clips,
        clipping_type: clippingType,
        individual_clips: individualClips
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/clip/batch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            const result = await response.json();
            currentJobId = result.job_id;
            showJobStatus(result.job_id, true);
            startBatchStatusCheck();
        } else {
            const error = await response.json();
            alert(`오류: ${error.detail}`);
        }
    } catch (error) {
        alert(`요청 실패: ${error.message}`);
    }
}

// 작업 상태 표시
function showJobStatus(jobId, isBatch = false) {
    const jobStatus = document.getElementById('job-status');
    jobStatus.classList.remove('hidden');
    
    document.querySelector('.job-id').textContent = `Job ID: ${jobId}`;
    updateStatusUI('pending', 0, '작업 대기 중...');
}

// 상태 체크 시작
function startStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    
    statusCheckInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/status/${currentJobId}`);
            if (response.ok) {
                const status = await response.json();
                updateStatusUI(status.status, status.progress, status.message);
                
                if (status.status === 'completed') {
                    clearInterval(statusCheckInterval);
                    showDownloadButton();
                    addToRecentJobs(status);
                } else if (status.status === 'failed') {
                    clearInterval(statusCheckInterval);
                    alert(`작업 실패: ${status.error || status.message}`);
                }
            }
        } catch (error) {
            console.error('Status check error:', error);
        }
    }, 1000);
}

// 배치 상태 체크
function startBatchStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    
    statusCheckInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/batch/status/${currentJobId}`);
            if (response.ok) {
                const status = await response.json();
                const message = `${status.message} (${status.completed_clips || 0}/${status.total_clips || 0})`;
                updateStatusUI(status.status, status.progress, message);
                
                if (status.status === 'completed') {
                    clearInterval(statusCheckInterval);
                    showBatchDownloadOptions(status.output_files);
                    addToRecentJobs(status, true);
                } else if (status.status === 'failed') {
                    clearInterval(statusCheckInterval);
                    alert(`배치 작업 실패: ${status.error || status.message}`);
                }
            }
        } catch (error) {
            console.error('Batch status check error:', error);
        }
    }, 2000);
}

// 상태 UI 업데이트
function updateStatusUI(status, progress, message) {
    const statusBadge = document.querySelector('.status-badge');
    const progressBar = document.querySelector('.progress-bar');
    const progressText = document.querySelector('.progress-text');
    const statusMessage = document.querySelector('.status-message');
    
    // 상태 배지 업데이트
    statusBadge.className = 'status-badge ' + status;
    statusBadge.textContent = {
        'pending': '대기 중',
        'processing': '처리 중',
        'completed': '완료',
        'failed': '실패'
    }[status] || status;
    
    // 진행률 업데이트
    progressBar.style.width = progress + '%';
    progressText.textContent = progress + '%';
    
    // 메시지 업데이트
    statusMessage.textContent = message;
}

// 다운로드 버튼 표시
function showDownloadButton() {
    document.querySelector('.download-btn').classList.remove('hidden');
}

// 배치 다운로드 옵션 표시
function showBatchDownloadOptions(outputFiles) {
    const actionButtons = document.querySelector('.action-buttons');
    actionButtons.innerHTML = '';
    
    outputFiles.forEach(file => {
        const btn = document.createElement('button');
        btn.className = 'download-btn';
        btn.textContent = `클립 ${file.clip_num} 다운로드`;
        btn.onclick = () => downloadBatchClip(currentJobId, file.clip_num);
        actionButtons.appendChild(btn);
    });
    
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'cancel-btn';
    cancelBtn.textContent = '닫기';
    cancelBtn.onclick = cancelJob;
    actionButtons.appendChild(cancelBtn);
}

// 클립 다운로드
async function downloadClip() {
    if (!currentJobId) return;
    
    window.open(`${API_BASE_URL}/api/download/${currentJobId}`, '_blank');
}

// 배치 클립 다운로드
async function downloadBatchClip(jobId, clipNum) {
    window.open(`${API_BASE_URL}/api/batch/download/${jobId}/${clipNum}`, '_blank');
}

// 작업 취소
function cancelJob() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    document.getElementById('job-status').classList.add('hidden');
    currentJobId = null;
}

// 최근 작업 추가
function addToRecentJobs(jobData, isBatch = false) {
    const recentJobs = JSON.parse(localStorage.getItem('recentJobs') || '[]');
    
    recentJobs.unshift({
        jobId: jobData.job_id,
        timestamp: new Date().toISOString(),
        isBatch: isBatch,
        status: jobData.status,
        outputFile: jobData.output_file,
        outputFiles: jobData.output_files
    });
    
    // 최대 10개만 유지
    recentJobs.splice(10);
    
    localStorage.setItem('recentJobs', JSON.stringify(recentJobs));
    loadRecentJobs();
}

// 최근 작업 로드
function loadRecentJobs() {
    const recentJobs = JSON.parse(localStorage.getItem('recentJobs') || '[]');
    const recentJobsContainer = document.getElementById('recent-jobs');
    
    if (recentJobs.length === 0) {
        recentJobsContainer.innerHTML = '<p style="color: #999;">최근 작업이 없습니다.</p>';
        return;
    }
    
    recentJobsContainer.innerHTML = '';
    
    recentJobs.forEach(job => {
        const jobItem = document.createElement('div');
        jobItem.className = 'job-item';
        
        const jobInfo = document.createElement('div');
        jobInfo.className = 'job-info';
        jobInfo.innerHTML = `
            <div class="job-item-id">${job.jobId}</div>
            <div class="job-item-time">${new Date(job.timestamp).toLocaleString()}</div>
        `;
        
        const jobActions = document.createElement('div');
        jobActions.className = 'job-actions';
        
        if (job.status === 'completed') {
            if (job.isBatch && job.outputFiles) {
                const select = document.createElement('select');
                select.innerHTML = '<option>다운로드...</option>';
                job.outputFiles.forEach(file => {
                    const option = document.createElement('option');
                    option.value = file.clip_num;
                    option.textContent = `클립 ${file.clip_num}`;
                    select.appendChild(option);
                });
                select.onchange = (e) => {
                    if (e.target.value !== '다운로드...') {
                        downloadBatchClip(job.jobId, parseInt(e.target.value));
                    }
                };
                jobActions.appendChild(select);
            } else if (job.outputFile) {
                const downloadBtn = document.createElement('button');
                downloadBtn.className = 'download-btn';
                downloadBtn.textContent = '다운로드';
                downloadBtn.onclick = () => window.open(`${API_BASE_URL}/api/download/${job.jobId}`, '_blank');
                jobActions.appendChild(downloadBtn);
            }
        }
        
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'cancel-btn';
        deleteBtn.textContent = '삭제';
        deleteBtn.onclick = () => deleteJob(job.jobId);
        jobActions.appendChild(deleteBtn);
        
        jobItem.appendChild(jobInfo);
        jobItem.appendChild(jobActions);
        recentJobsContainer.appendChild(jobItem);
    });
}

// 작업 삭제
async function deleteJob(jobId) {
    if (!confirm('이 작업을 삭제하시겠습니까?')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/job/${jobId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            // 로컬 스토리지에서도 제거
            const recentJobs = JSON.parse(localStorage.getItem('recentJobs') || '[]');
            const filtered = recentJobs.filter(job => job.jobId !== jobId);
            localStorage.setItem('recentJobs', JSON.stringify(filtered));
            loadRecentJobs();
        }
    } catch (error) {
        console.error('Delete job error:', error);
    }
}

// 폼 초기화
function clearSingleClipForm() {
    document.getElementById('start-time').value = '';
    document.getElementById('end-time').value = '';
    document.getElementById('text-eng').value = '';
    document.getElementById('text-kor').value = '';
    document.getElementById('note').value = '';
    document.getElementById('keywords').value = '';
}

// API 상태 체크
async function checkAPIStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api`);
        if (!response.ok) {
            alert('API 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
        }
    } catch (error) {
        alert('API 서버에 연결할 수 없습니다.\n\n다음 명령어로 서버를 실행하세요:\npython3 clipping_api.py');
    }
}

// 페이지 로드 시 API 상태 체크
checkAPIStatus();
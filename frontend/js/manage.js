// 클립 관리 페이지 스크립트

// 최근 작업 목록 로드
async function loadRecentJobs() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/jobs/recent?limit=20`);
        if (!response.ok) {
            throw new Error('Failed to load jobs');
        }
        
        const jobs = await response.json();
        displayJobs(jobs);
    } catch (error) {
        console.error('Error loading jobs:', error);
        showError('작업 목록을 불러올 수 없습니다.');
    }
}

// 현재 뷰 모드 (기본값: grid)
let currentView = localStorage.getItem('jobsViewMode') || 'grid';

// 작업 목록 표시
function displayJobs(jobs) {
    // 저장된 뷰 모드 적용
    if (currentView === 'grid') {
        displayJobsGrid(jobs);
        document.getElementById('grid-view-btn')?.classList.add('active');
        document.getElementById('list-view-btn')?.classList.remove('active');
        document.getElementById('jobs-grid').style.display = 'grid';
        document.getElementById('jobs-table').style.display = 'none';
    } else {
        displayJobsList(jobs);
        document.getElementById('list-view-btn')?.classList.add('active');
        document.getElementById('grid-view-btn')?.classList.remove('active');
        document.getElementById('jobs-table').style.display = 'block';
        document.getElementById('jobs-grid').style.display = 'none';
    }
}

// 리스트 뷰 표시
function displayJobsList(jobs) {
    const tbody = document.getElementById('jobs-list');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (jobs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--gray-500);">작업이 없습니다</td></tr>';
        return;
    }
    
    jobs.forEach(job => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${formatDate(job.created_at)}</td>
            <td title="${job.media_path}">${job.media_filename || 'N/A'}</td>
            <td>${job.start_time?.toFixed(1)}s - ${job.end_time?.toFixed(1)}s</td>
            <td>Type ${job.clipping_type}</td>
            <td><span class="status-badge ${job.status}">${getStatusText(job.status)}</span></td>
            <td>
                ${job.status === 'completed' ? 
                    `<button class="preview-btn" onclick="previewVideo('${job.id}')">미리보기</button>
                     <button class="download-btn" onclick="downloadJob('${job.id}')">다운로드</button>` : 
                    `<button class="cancel-btn" onclick="deleteJob('${job.id}')">삭제</button>`}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 그리드 뷰 표시
function displayJobsGrid(jobs) {
    const grid = document.getElementById('jobs-grid');
    if (!grid) return;
    
    grid.innerHTML = '';
    
    if (jobs.length === 0) {
        grid.innerHTML = '<div style="text-align: center; color: var(--gray-500); grid-column: 1/-1;">작업이 없습니다</div>';
        return;
    }
    
    jobs.forEach(job => {
        const card = document.createElement('div');
        card.className = 'job-card';
        card.innerHTML = `
            <div class="job-card-thumbnail">
                ${job.status === 'completed' ? 
                    `<video src="${API_BASE_URL}/api/video/${job.id}" muted preload="metadata"></video>` :
                    `<div class="no-preview">미리보기 없음</div>`
                }
                <span class="job-card-status ${job.status}">${getStatusText(job.status)}</span>
            </div>
            <div class="job-card-body">
                <div class="job-card-title" title="${job.media_path}">
                    ${job.media_filename || 'N/A'}
                </div>
                <div class="job-card-info">
                    <div>${formatDate(job.created_at)}</div>
                    <div>${job.start_time?.toFixed(1)}s - ${job.end_time?.toFixed(1)}s | Type ${job.clipping_type}</div>
                </div>
                <div class="job-card-actions">
                    ${job.status === 'completed' ? 
                        `<button class="preview-btn" onclick="previewVideo('${job.id}')">미리보기</button>
                         <button class="download-btn" onclick="downloadJob('${job.id}')">다운로드</button>` : 
                        `<button class="delete-btn" onclick="deleteJob('${job.id}')">삭제</button>`
                    }
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

// 뷰 전환
function switchView(view) {
    currentView = view;
    localStorage.setItem('jobsViewMode', view);
    loadRecentJobs();
}

// 작업 새로고침
async function refreshJobs() {
    const status = document.getElementById('filter-status')?.value;
    const period = document.getElementById('filter-period')?.value;
    
    // 현재는 단순히 최근 목록만 로드
    // TODO: 필터 적용된 검색 구현
    await loadRecentJobs();
}

// 작업 다운로드
function downloadJob(jobId) {
    window.open(`${API_BASE_URL}/api/download/${jobId}`, '_blank');
}

// 비디오 미리보기
function previewVideo(jobId) {
    const modal = document.getElementById('video-preview-modal');
    const video = document.getElementById('preview-video');
    
    if (!modal || !video) {
        // 모달이 없으면 생성
        createVideoPreviewModal();
        return previewVideo(jobId);
    }
    
    // 비디오 소스 설정
    video.src = `${API_BASE_URL}/api/video/${jobId}`;
    video.load();
    
    // 모달 표시
    modal.style.display = 'block';
    
    // ESC 키로 닫기
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeVideoPreview();
        }
    });
}

// 비디오 미리보기 닫기
function closeVideoPreview() {
    const modal = document.getElementById('video-preview-modal');
    const video = document.getElementById('preview-video');
    
    if (modal) {
        modal.style.display = 'none';
    }
    
    if (video) {
        video.pause();
        video.src = '';
    }
}

// 비디오 미리보기 모달 생성
function createVideoPreviewModal() {
    const modal = document.createElement('div');
    modal.id = 'video-preview-modal';
    modal.className = 'video-modal';
    modal.innerHTML = `
        <div class="video-modal-content">
            <div class="video-modal-header">
                <h3>비디오 미리보기</h3>
                <button class="video-modal-close" onclick="closeVideoPreview()">&times;</button>
            </div>
            <div class="video-modal-body">
                <video id="preview-video" controls width="100%" height="auto">
                    브라우저가 비디오를 지원하지 않습니다.
                </video>
            </div>
        </div>
    `;
    
    // 모달 외부 클릭 시 닫기
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeVideoPreview();
        }
    });
    
    document.body.appendChild(modal);
}

// 작업 삭제
async function deleteJob(jobId) {
    if (!confirm('이 작업을 삭제하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/job/${jobId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showSuccess('작업이 삭제되었습니다.');
            await loadRecentJobs();
        } else {
            throw new Error('삭제 실패');
        }
    } catch (error) {
        console.error('Delete failed:', error);
        showError('작업 삭제에 실패했습니다.');
    }
}
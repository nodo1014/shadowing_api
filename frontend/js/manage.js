// 클립 관리 페이지 스크립트

// 전체 작업 목록 저장
let allJobs = [];
let currentView = 'grid'; // 기본 뷰 모드를 썸네일(grid)로 변경

// 최근 작업 목록 로드 (최신순 정렬)
async function loadRecentJobs() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/jobs/recent?limit=100`);
        if (!response.ok) {
            throw new Error('Failed to load jobs');
        }
        
        allJobs = await response.json();
        // 최신순으로 정렬 (이미 정렬되어 있을 수 있지만 확실하게)
        allJobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        applyFilters();
    } catch (error) {
        console.error('Error loading jobs:', error);
        const tbody = document.getElementById('jobs-list');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--danger);">작업 목록을 불러올 수 없습니다.</td></tr>';
        }
    }
}

// 작업 목록 표시
function displayJobs(jobs) {
    if (currentView === 'grid') {
        displayJobsGrid(jobs);
    } else {
        displayJobsList(jobs);
    }
}

// 리스트 뷰 표시
function displayJobsList(jobs) {
    const tbody = document.getElementById('jobs-list');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    selectedJobs.clear(); // 선택 초기화
    
    if (jobs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--gray-500);">작업이 없습니다</td></tr>';
        return;
    }
    
    jobs.forEach(job => {
        const tr = document.createElement('tr');
        const mediaName = job.media_path ? job.media_path.split('/').pop() : 'N/A';
        const templateType = job.template_number ? `Template ${job.template_number}` : `Type ${job.clipping_type || 1}`;
        
        tr.innerHTML = `
            <td>
                <input type="checkbox" class="job-checkbox" data-job-id="${job.id}" 
                       onchange="toggleJobSelection('${job.id}', this)">
            </td>
            <td>${formatDate(job.created_at)}</td>
            <td title="${job.media_path || ''}">${mediaName}</td>
            <td>${job.start_time ? job.start_time.toFixed(1) : '0'}s - ${job.end_time ? job.end_time.toFixed(1) : '0'}s</td>
            <td>${templateType}</td>
            <td><span class="status-badge ${job.status}">${getStatusText(job.status)}</span></td>
            <td>${job.text_eng || '-'}</td>
            <td>
                ${job.status === 'completed' && job.output_file ? 
                    `<button class="download-btn" onclick="downloadJob('${job.id}')">다운로드</button>` : 
                    `<button class="delete-btn" onclick="deleteJob('${job.id}')">삭제</button>`}
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    updateBulkActions();
}


// 필터 적용
window.applyFilters = function() {
    const statusFilter = document.getElementById('filter-status')?.value;
    const periodFilter = document.getElementById('filter-period')?.value || 'all';
    
    let filteredJobs = [...allJobs];
    
    // 상태 필터
    if (statusFilter) {
        filteredJobs = filteredJobs.filter(job => job.status === statusFilter);
    }
    
    // 기간 필터
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    if (periodFilter === 'today') {
        filteredJobs = filteredJobs.filter(job => {
            const jobDate = new Date(job.created_at);
            return jobDate >= today;
        });
    } else if (periodFilter === 'week') {
        const weekAgo = new Date(today);
        weekAgo.setDate(weekAgo.getDate() - 7);
        filteredJobs = filteredJobs.filter(job => {
            const jobDate = new Date(job.created_at);
            return jobDate >= weekAgo;
        });
    } else if (periodFilter === 'month') {
        const monthAgo = new Date(today);
        monthAgo.setMonth(monthAgo.getMonth() - 1);
        filteredJobs = filteredJobs.filter(job => {
            const jobDate = new Date(job.created_at);
            return jobDate >= monthAgo;
        });
    }
    
    displayJobs(filteredJobs);
}

// 그리드 뷰 표시
function displayJobsGrid(jobs) {
    const grid = document.getElementById('jobs-grid');
    if (!grid) return;
    
    grid.innerHTML = '';
    selectedJobs.clear(); // 선택 초기화
    
    if (jobs.length === 0) {
        grid.innerHTML = '<div style="text-align: center; color: var(--gray-500); width: 100%; padding: 40px;">작업이 없습니다</div>';
        return;
    }
    
    jobs.forEach(job => {
        const card = document.createElement('div');
        card.className = 'job-card';
        const mediaName = job.media_path ? job.media_path.split('/').pop() : 'N/A';
        const templateType = job.template_number ? `Template ${job.template_number}` : `Type ${job.clipping_type || 1}`;
        
        // 비디오 미리보기 생성
        const thumbnailContent = job.status === 'completed' && job.output_file ? 
            `<video src="${API_BASE_URL}/api/video/${job.id}" 
                    controls
                    controlsList="nodownload"
                    preload="metadata" 
                    onloadedmetadata="this.currentTime = 0.1"
                    onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
            </video>
            <div class="no-preview" style="display: none;">
                <span>미리보기 없음</span>
            </div>` :
            `<div class="no-preview">
                <span>${job.status === 'processing' ? '처리중...' : '미리보기 없음'}</span>
            </div>`;
        
        card.innerHTML = `
            <div class="job-card-selection">
                <input type="checkbox" class="job-checkbox" data-job-id="${job.id}" 
                       onchange="toggleJobSelection('${job.id}', this)">
            </div>
            <div class="job-card-thumbnail">
                ${thumbnailContent}
                <span class="job-card-status ${job.status}">${getStatusText(job.status)}</span>
            </div>
            <div class="job-card-body">
                <div class="job-card-header">
                    <div class="job-card-title" title="${job.media_path || ''}">${mediaName}</div>
                    <div class="job-card-template">${templateType}</div>
                </div>
                <div class="job-card-info">
                    <div class="job-card-date">${formatDate(job.created_at)}</div>
                    <div class="job-card-details">
                        <span class="time-range">${job.start_time ? job.start_time.toFixed(1) : '0'}s - ${job.end_time ? job.end_time.toFixed(1) : '0'}s</span>
                        <span class="duration">(${job.start_time && job.end_time ? (job.end_time - job.start_time).toFixed(1) : '0'}초)</span>
                    </div>
                    <div class="job-card-text" title="${job.text_eng || ''}">${job.text_eng || '-'}</div>
                </div>
                <div class="job-card-actions">
                    ${job.status === 'completed' && job.output_file ? 
                        `<button class="download-btn" onclick="downloadJob('${job.id}')">다운로드</button>` : 
                        `<button class="delete-btn" onclick="deleteJob('${job.id}')">삭제</button>`}
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
    
    updateBulkActions();
}

// 뷰 전환
window.switchView = function(view) {
    currentView = view;
    
    // 버튼 활성화 상태 변경
    const listBtn = document.getElementById('list-view-btn');
    const gridBtn = document.getElementById('grid-view-btn');
    
    if (listBtn && gridBtn) {
        listBtn.classList.toggle('active', view === 'list');
        gridBtn.classList.toggle('active', view === 'grid');
    }
    
    // 뷰 표시/숨김
    const tableView = document.getElementById('jobs-table');
    const gridView = document.getElementById('jobs-grid');
    
    if (tableView && gridView) {
        if (view === 'grid') {
            tableView.classList.add('hidden');
            gridView.classList.remove('hidden');
        } else {
            tableView.classList.remove('hidden');
            gridView.classList.add('hidden');
        }
    }
    
    // 데이터 다시 표시
    applyFilters();
}

// 작업 새로고침
window.refreshJobs = async function() {
    await loadRecentJobs();
}

// 작업 다운로드
window.downloadJob = function(jobId) {
    window.open(`${API_BASE_URL}/api/download/${jobId}`, '_blank');
}

// 작업 삭제
window.deleteJob = async function(jobId) {
    if (!confirm('이 작업을 삭제하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/job/${jobId}?force=true`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showSuccess('작업이 삭제되었습니다.');
            await loadRecentJobs();
        } else {
            // 파일이 없어도 DB에서 삭제 시도
            const forceResponse = await fetch(`${API_BASE_URL}/api/job/${jobId}?force=true`, {
                method: 'DELETE'
            });
            if (forceResponse.ok) {
                showSuccess('DB 레코드가 삭제되었습니다.');
                await loadRecentJobs();
            } else {
                throw new Error('삭제 실패');
            }
        }
    } catch (error) {
        console.error('Delete failed:', error);
        showError('작업 삭제에 실패했습니다.');
    }
}

// 비디오 재생
window.playVideo = function(jobId) {
    const video = document.querySelector(`.job-card video[src*="${jobId}"]`);
    if (video) {
        if (video.paused) {
            video.play();
        } else {
            video.pause();
        }
    }
}

// 선택된 항목 추적
let selectedJobs = new Set();

// 선택 토글
window.toggleJobSelection = function(jobId, checkbox) {
    if (checkbox.checked) {
        selectedJobs.add(jobId);
    } else {
        selectedJobs.delete(jobId);
    }
    updateBulkActions();
}

// 전체 선택/해제
window.toggleAllJobs = function(checkbox) {
    const checkboxes = document.querySelectorAll('.job-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checkbox.checked;
        const jobId = cb.getAttribute('data-job-id');
        if (checkbox.checked) {
            selectedJobs.add(jobId);
        } else {
            selectedJobs.delete(jobId);
        }
    });
    updateBulkActions();
}

// 대량 작업 버튼 업데이트
function updateBulkActions() {
    const bulkDeleteBtn = document.getElementById('bulk-delete-btn');
    if (bulkDeleteBtn) {
        bulkDeleteBtn.style.display = selectedJobs.size > 0 ? 'inline-block' : 'none';
        bulkDeleteBtn.textContent = `선택 삭제 (${selectedJobs.size})`;
    }
}

// 선택 항목 삭제
window.deleteSelectedJobs = async function() {
    if (selectedJobs.size === 0) {
        showError('선택된 항목이 없습니다.');
        return;
    }
    
    if (!confirm(`선택된 ${selectedJobs.size}개 항목을 삭제하시겠습니까?\n(파일이 없어도 DB 기록은 삭제됩니다)`)) {
        return;
    }
    
    let successCount = 0;
    let failCount = 0;
    
    for (const jobId of selectedJobs) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/job/${jobId}?force=true`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                successCount++;
            } else {
                failCount++;
            }
        } catch (error) {
            failCount++;
        }
    }
    
    if (successCount > 0) {
        showSuccess(`${successCount}개 항목이 삭제되었습니다.`);
    }
    if (failCount > 0) {
        showError(`${failCount}개 항목 삭제에 실패했습니다.`);
    }
    
    selectedJobs.clear();
    await loadRecentJobs();
}

// DB 정리 - 파일이 없는 레코드 삭제
window.cleanupOrphanedRecords = async function() {
    if (!confirm('파일이 없는 DB 레코드를 모두 정리하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/cleanup`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            showSuccess(`${result.deleted_count}개의 고아 레코드가 정리되었습니다.`);
            await loadRecentJobs();
        } else {
            throw new Error('정리 실패');
        }
    } catch (error) {
        console.error('Cleanup failed:', error);
        showError('DB 정리에 실패했습니다.');
    }
}
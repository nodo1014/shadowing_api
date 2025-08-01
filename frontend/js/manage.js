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

// 작업 목록 표시
function displayJobs(jobs) {
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
                    `<button class="download-btn" onclick="downloadJob('${job.id}')">다운로드</button>` : 
                    `<button class="cancel-btn" onclick="deleteJob('${job.id}')">삭제</button>`}
            </td>
        `;
        tbody.appendChild(tr);
    });
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
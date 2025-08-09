// YouTube 업로드 관련 기능

let youtubeAuthenticated = false;
let youtubeChannel = null;

// YouTube 인증 상태 확인
async function checkYouTubeAuth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/youtube/status`);
        if (!response.ok) {
            // YouTube API가 없는 경우 기본값 반환
            console.warn('YouTube API not available');
            return false;
        }
        const data = await response.json();
        
        youtubeAuthenticated = data.authenticated;
        youtubeChannel = data.channel;
        
        updateYouTubeUI();
        return data.authenticated;
    } catch (error) {
        console.error('YouTube auth check failed:', error);
        return false;
    }
}

// YouTube UI 업데이트
function updateYouTubeUI() {
    const authStatus = document.getElementById('youtube-auth-status');
    if (authStatus) {
        if (youtubeAuthenticated && youtubeChannel) {
            authStatus.innerHTML = `
                <div class="youtube-connected">
                    <span class="status-icon">✓</span>
                    <span>YouTube 연결됨: ${youtubeChannel.title}</span>
                    <button class="btn-small" onclick="disconnectYouTube()">연결 해제</button>
                </div>
            `;
        } else {
            authStatus.innerHTML = `
                <div class="youtube-disconnected">
                    <span class="status-icon">✗</span>
                    <span>YouTube 연결 안됨</span>
                    <button class="btn-small btn-primary" onclick="connectYouTube()">YouTube 연결</button>
                </div>
            `;
        }
    }
}

// YouTube 연결
async function connectYouTube() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/youtube/auth`);
        const data = await response.json();
        
        if (data.auth_url) {
            // 새 창에서 OAuth2 인증 페이지 열기
            const authWindow = window.open(data.auth_url, 'youtube_auth', 'width=600,height=700');
            
            // 인증 완료 메시지 리스너
            window.addEventListener('message', async (event) => {
                if (event.data.type === 'youtube_auth_success') {
                    youtubeAuthenticated = true;
                    youtubeChannel = event.data.channel;
                    updateYouTubeUI();
                    showSuccess('YouTube 연결 성공!');
                    
                    // 인증 창 닫기
                    if (authWindow && !authWindow.closed) {
                        authWindow.close();
                    }
                }
            });
        }
    } catch (error) {
        console.error('YouTube connection failed:', error);
        showError('YouTube 연결 실패: ' + error.message);
    }
}

// YouTube 연결 해제
function disconnectYouTube() {
    // 로컬 상태만 업데이트 (실제 토큰은 서버에 유지)
    youtubeAuthenticated = false;
    youtubeChannel = null;
    updateYouTubeUI();
    showInfo('YouTube 연결이 해제되었습니다');
}

// YouTube 업로드 모달 표시
function showYouTubeUploadModal(jobId) {
    if (!youtubeAuthenticated) {
        showError('먼저 YouTube에 연결해주세요');
        connectYouTube();
        return;
    }
    
    // 작업 정보 가져오기
    const job = allJobs.find(j => j.id === jobId);
    if (!job) {
        showError('작업을 찾을 수 없습니다');
        return;
    }
    
    // 모달 HTML 생성
    const modal = document.createElement('div');
    modal.className = 'youtube-upload-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeYouTubeModal()"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h2>YouTube에 업로드</h2>
                <button class="close-btn" onclick="closeYouTubeModal()">×</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>제목 *</label>
                    <input type="text" id="youtube-title" value="${job.text_eng || 'Shadowing Video'}" maxlength="100">
                </div>
                <div class="form-group">
                    <label>설명</label>
                    <textarea id="youtube-description" rows="4">${generateDescription(job)}</textarea>
                </div>
                <div class="form-group">
                    <label>태그 (쉼표로 구분)</label>
                    <input type="text" id="youtube-tags" value="shadowing, 영어공부, 영어듣기, ${job.keywords ? job.keywords.join(', ') : ''}">
                </div>
                <div class="form-group">
                    <label>공개 설정</label>
                    <select id="youtube-privacy">
                        <option value="private">비공개</option>
                        <option value="unlisted">일부 공개 (링크 있는 사용자만)</option>
                        <option value="public">공개</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeYouTubeModal()">취소</button>
                <button class="btn btn-primary" onclick="uploadToYouTube('${jobId}')">
                    <span id="upload-btn-text">업로드</span>
                    <span id="upload-spinner" class="spinner hidden"></span>
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// YouTube 업로드 설명 생성
function generateDescription(job) {
    let description = `🎯 Shadowing Practice Video\n\n`;
    
    if (job.text_eng) {
        description += `📝 English: ${job.text_eng}\n`;
    }
    if (job.text_kor) {
        description += `📝 Korean: ${job.text_kor}\n`;
    }
    if (job.note) {
        description += `💡 Note: ${job.note}\n`;
    }
    
    description += `\n⏱️ Duration: ${job.start_time}s - ${job.end_time}s\n`;
    
    if (job.template_number) {
        description += `📚 Template: Template ${job.template_number}\n`;
    }
    
    description += `\n🔗 Created with Shadowing Maker`;
    
    return description;
}

// YouTube 모달 닫기
function closeYouTubeModal() {
    const modal = document.querySelector('.youtube-upload-modal');
    if (modal) {
        modal.remove();
    }
}

// YouTube에 업로드
async function uploadToYouTube(jobId) {
    const title = document.getElementById('youtube-title').value.trim();
    const description = document.getElementById('youtube-description').value.trim();
    const tags = document.getElementById('youtube-tags').value.split(',').map(t => t.trim()).filter(t => t);
    const privacyStatus = document.getElementById('youtube-privacy').value;
    
    if (!title) {
        showError('제목을 입력해주세요');
        return;
    }
    
    // 버튼 상태 변경
    const uploadBtn = document.querySelector('.modal-footer .btn-primary');
    const btnText = document.getElementById('upload-btn-text');
    const spinner = document.getElementById('upload-spinner');
    
    uploadBtn.disabled = true;
    btnText.textContent = '업로드 중...';
    spinner.classList.remove('hidden');
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/youtube/upload`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_id: jobId,
                title: title,
                description: description,
                tags: tags,
                privacy_status: privacyStatus
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
        
        const result = await response.json();
        
        showSuccess('YouTube 업로드가 시작되었습니다!');
        closeYouTubeModal();
        
        // 상태 업데이트를 위해 작업 목록 새로고침
        setTimeout(() => {
            refreshJobs();
        }, 2000);
        
    } catch (error) {
        console.error('Upload failed:', error);
        showError('업로드 실패: ' + error.message);
        
        // 버튼 상태 복원
        uploadBtn.disabled = false;
        btnText.textContent = '업로드';
        spinner.classList.add('hidden');
    }
}

// 페이지 로드 시 YouTube 인증 상태 확인
document.addEventListener('DOMContentLoaded', () => {
    checkYouTubeAuth();
});
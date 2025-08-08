// YouTube API 설정 관련 기능

// 현재 설정 로드
async function loadYouTubeSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/youtube/settings`);
        if (response.ok) {
            const settings = await response.json();
            
            // 폼에 값 설정
            document.getElementById('client-id').value = settings.client_id || '';
            document.getElementById('client-secret').value = settings.client_secret || '';
            document.getElementById('project-id').value = settings.project_id || '';
            
            // 상태 표시
            updateSettingsStatus(settings.configured);
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
        showError('설정을 불러올 수 없습니다');
    }
}

// 설정 저장
async function saveYouTubeSettings() {
    const clientId = document.getElementById('client-id').value.trim();
    const clientSecret = document.getElementById('client-secret').value.trim();
    const projectId = document.getElementById('project-id').value.trim();
    
    if (!clientId || !clientSecret) {
        showError('Client ID와 Client Secret은 필수입니다');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/youtube/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                client_id: clientId,
                client_secret: clientSecret,
                project_id: projectId || 'shadowing-maker'
            })
        });
        
        if (response.ok) {
            showSuccess('설정이 저장되었습니다');
            updateSettingsStatus(true);
            
            // YouTube 인증 상태 다시 확인
            if (typeof checkYouTubeAuth === 'function') {
                checkYouTubeAuth();
            }
        } else {
            const error = await response.json();
            showError('설정 저장 실패: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Save settings error:', error);
        showError('설정 저장 중 오류가 발생했습니다');
    }
}

// 설정 상태 업데이트
function updateSettingsStatus(configured) {
    const statusEl = document.getElementById('settings-status');
    if (statusEl) {
        if (configured) {
            statusEl.innerHTML = `
                <div class="status-configured">
                    <span class="status-icon">✓</span>
                    <span>API 설정 완료</span>
                </div>
            `;
        } else {
            statusEl.innerHTML = `
                <div class="status-not-configured">
                    <span class="status-icon">✗</span>
                    <span>API 설정 필요</span>
                </div>
            `;
        }
    }
}

// 설정 테스트
async function testYouTubeSettings() {
    const testBtn = document.getElementById('test-settings-btn');
    const originalText = testBtn.textContent;
    testBtn.disabled = true;
    testBtn.textContent = '테스트 중...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/youtube/settings/test`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showSuccess('API 설정이 올바릅니다');
            } else {
                showError('API 설정 테스트 실패: ' + (result.error || 'Unknown error'));
            }
        } else {
            showError('테스트 요청 실패');
        }
    } catch (error) {
        console.error('Test error:', error);
        showError('테스트 중 오류가 발생했습니다');
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = originalText;
    }
}

// 설정 초기화
function clearYouTubeSettings() {
    if (!confirm('정말로 API 설정을 초기화하시겠습니까?')) {
        return;
    }
    
    document.getElementById('client-id').value = '';
    document.getElementById('client-secret').value = '';
    document.getElementById('project-id').value = '';
    
    showInfo('설정이 초기화되었습니다. 저장 버튼을 클릭하여 적용하세요.');
}

// 페이지 로드 시 설정 불러오기
document.addEventListener('DOMContentLoaded', () => {
    // settings 페이지가 활성화될 때만 로드
    const settingsPage = document.getElementById('settings-page');
    if (settingsPage) {
        loadYouTubeSettings();
    }
});
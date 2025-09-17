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

// 렌더링 설정 관련 함수들
async function loadRenderingSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings`);
        if (response.ok) {
            const settings = await response.json();
            
            // TTS 설정
            document.getElementById('render-voice-korean').value = settings.tts.voice_korean;
            document.getElementById('render-voice-english').value = settings.tts.voice_english;
            document.getElementById('render-tts-speed').value = settings.tts.speed;
            document.getElementById('render-tts-volume').value = settings.tts.volume;
            
            // 비디오 설정
            document.getElementById('render-video-crf').value = settings.video.crf;
            document.getElementById('render-video-preset').value = settings.video.preset;
            document.getElementById('render-video-resolution').value = settings.video.resolution;
            document.getElementById('render-video-framerate').value = settings.video.framerate;
            
            // 자막 설정
            document.getElementById('render-subtitle-size-english').value = settings.subtitle.size_english;
            document.getElementById('render-subtitle-size-korean').value = settings.subtitle.size_korean;
            document.getElementById('render-subtitle-color-english').value = settings.subtitle.color_english;
            document.getElementById('render-subtitle-color-korean').value = settings.subtitle.color_korean;
            
            // 쇼츠 설정
            document.getElementById('render-shorts-aspect').value = settings.shorts.aspect_ratio;
            document.getElementById('render-thumbnail-darken').value = settings.shorts.thumbnail_darken;
            document.getElementById('render-gap-duration').value = settings.template.gap_duration;
            document.getElementById('render-show-title').checked = settings.template.show_title;
            
            // Range 값 표시 업데이트
            updateRangeValues();
            
            showSuccess('렌더링 설정을 불러왔습니다.');
        }
    } catch (error) {
        console.error('Failed to load rendering settings:', error);
        showError('렌더링 설정을 불러올 수 없습니다');
    }
}

async function saveRenderingSettings() {
    const settings = {
        tts: {
            voice_korean: document.getElementById('render-voice-korean').value,
            voice_english: document.getElementById('render-voice-english').value,
            speed: parseInt(document.getElementById('render-tts-speed').value),
            pitch: 0, // 현재 UI에 없음
            volume: parseInt(document.getElementById('render-tts-volume').value)
        },
        video: {
            crf: parseInt(document.getElementById('render-video-crf').value),
            preset: document.getElementById('render-video-preset').value,
            resolution: document.getElementById('render-video-resolution').value,
            framerate: parseInt(document.getElementById('render-video-framerate').value)
        },
        subtitle: {
            font_english: "Noto Sans CJK KR",
            font_korean: "Noto Sans CJK KR",
            size_english: parseInt(document.getElementById('render-subtitle-size-english').value),
            size_korean: parseInt(document.getElementById('render-subtitle-size-korean').value),
            color_english: document.getElementById('render-subtitle-color-english').value,
            color_korean: document.getElementById('render-subtitle-color-korean').value,
            border_width: 3,
            border_color: "#000000",
            position: "bottom",
            margin_bottom: 300
        },
        template: {
            gap_duration: parseFloat(document.getElementById('render-gap-duration').value),
            fade_effect: false,
            show_title: document.getElementById('render-show-title').checked,
            background_music_volume: 20
        },
        shorts: {
            aspect_ratio: document.getElementById('render-shorts-aspect').value,
            thumbnail_darken: parseInt(document.getElementById('render-thumbnail-darken').value),
            intro_duration: 3
        },
        advanced: {
            hardware_accel: "none",
            threads: 0,
            temp_path: "/tmp",
            output_format: "mp4"
        }
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            showSuccess('렌더링 설정이 저장되었습니다.');
        } else {
            const error = await response.json();
            showError('렌더링 설정 저장 실패: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Save rendering settings error:', error);
        showError('렌더링 설정 저장 중 오류가 발생했습니다');
    }
}

async function resetRenderingSettings() {
    if (!confirm('렌더링 설정을 기본값으로 초기화하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/reset`, {
            method: 'POST'
        });
        
        if (response.ok) {
            await loadRenderingSettings();
            showSuccess('렌더링 설정이 초기화되었습니다.');
        } else {
            throw new Error('설정 초기화 실패');
        }
    } catch (error) {
        console.error('Reset rendering settings error:', error);
        showError('렌더링 설정 초기화 실패: ' + error.message);
    }
}

function updateRangeValues() {
    // 속도 값 업데이트
    const speedEl = document.getElementById('render-tts-speed');
    const speedValueEl = document.getElementById('render-speed-value');
    if (speedEl && speedValueEl) {
        speedValueEl.textContent = speedEl.value + '%';
    }
    
    // 볼륨 값 업데이트
    const volumeEl = document.getElementById('render-tts-volume');
    const volumeValueEl = document.getElementById('render-volume-value');
    if (volumeEl && volumeValueEl) {
        volumeValueEl.textContent = volumeEl.value + '%';
    }
    
    // 어둡게 값 업데이트
    const darkenEl = document.getElementById('render-thumbnail-darken');
    const darkenValueEl = document.getElementById('render-darken-value');
    if (darkenEl && darkenValueEl) {
        darkenValueEl.textContent = darkenEl.value + '%';
    }
}

// Range input 이벤트 리스너 설정
function setupRenderingSettingsListeners() {
    // 속도 슬라이더
    const speedEl = document.getElementById('render-tts-speed');
    if (speedEl) {
        speedEl.addEventListener('input', updateRangeValues);
    }
    
    // 볼륨 슬라이더
    const volumeEl = document.getElementById('render-tts-volume');
    if (volumeEl) {
        volumeEl.addEventListener('input', updateRangeValues);
    }
    
    // 어둡게 슬라이더
    const darkenEl = document.getElementById('render-thumbnail-darken');
    if (darkenEl) {
        darkenEl.addEventListener('input', updateRangeValues);
    }
}

// 페이지 로드 시 설정 불러오기
document.addEventListener('DOMContentLoaded', () => {
    // YouTube 설정 페이지
    const youtubeSettingsPage = document.getElementById('youtube-settings-page');
    if (youtubeSettingsPage) {
        loadYouTubeSettings();
    }
    
    // 렌더링 설정 페이지
    const renderSettingsPage = document.getElementById('render-settings-page');
    if (renderSettingsPage) {
        loadRenderingSettings();
        setupRenderingSettingsListeners();
    }
});
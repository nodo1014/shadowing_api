// API Base URL
const API_BASE_URL = window.location.origin;

// 상태 텍스트 변환
function getStatusText(status) {
    const statusMap = {
        'pending': '대기중',
        'processing': '처리중',
        'completed': '완료',
        'failed': '실패'
    };
    return statusMap[status] || status;
}

// 날짜 포맷
function formatDate(dateString) {
    return new Date(dateString).toLocaleString('ko-KR');
}

// 파일 크기 포맷
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1048576) return Math.round(bytes / 1024) + ' KB';
    else if (bytes < 1073741824) return Math.round(bytes / 1048576) + ' MB';
    else return Math.round(bytes / 1073741824) + ' GB';
}

// 오류 메시지 표시
function showError(message) {
    alert(`오류: ${message}`);
}

// 성공 메시지 표시
function showSuccess(message) {
    alert(message);
}
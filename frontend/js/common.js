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

// 날짜 포맷 - 한국시간(KST)으로 표시
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    const date = new Date(dateString);
    
    // 한국시간(KST, UTC+9)으로 변환하여 표시
    const options = {
        timeZone: 'Asia/Seoul',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    };
    
    return date.toLocaleString('ko-KR', options);
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
// 네비게이션 관리 스크립트

// 페이지 초기화 함수들
const pageInitializers = {
    'manage': loadRecentJobs,
    'batch': initBatchClips
};

// 페이지 전환
function switchPage(pageId) {
    // 모든 페이지 숨기기
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // 선택된 페이지 표시
    const selectedPage = document.getElementById(`${pageId}-page`);
    if (selectedPage) {
        selectedPage.classList.add('active');
        
        // 페이지별 초기화 함수 실행
        if (pageInitializers[pageId]) {
            pageInitializers[pageId]();
        }
    }
}

// 네비게이션 초기화
function initNavigation() {
    // 네비게이션 아이템 클릭 이벤트
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            // 네비게이션 활성화
            document.querySelectorAll('.nav-item').forEach(nav => {
                nav.classList.remove('active');
            });
            e.target.classList.add('active');
            
            // 페이지 전환
            const pageId = e.target.dataset.page;
            switchPage(pageId);
        });
    });
}

// DOM 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    
    // 첫 페이지 로드
    const firstPage = document.querySelector('.nav-item.active')?.dataset.page || 'manage';
    switchPage(firstPage);
});
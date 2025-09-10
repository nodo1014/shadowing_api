// YouTube Clone JavaScript - Interactive Features

document.addEventListener('DOMContentLoaded', function() {
    // Video Preview on Hover (Home Page)
    initVideoPreview();
    
    // Video Player Controls (Watch Page)
    initVideoPlayer();
    
    // Comment Interactions
    initCommentInteractions();
    
    // Search Functionality
    initSearch();
    
    // Sidebar Toggle
    initSidebarToggle();
});

function initVideoPreview() {
    const videoCards = document.querySelectorAll('.video-card');
    
    videoCards.forEach(card => {
        const video = card.querySelector('.video-thumbnail');
        const playButton = card.querySelector('.video-preview-controls');
        let hoverTimeout;
        
        card.addEventListener('mouseenter', () => {
            hoverTimeout = setTimeout(() => {
                if (video && video.tagName === 'VIDEO') {
                    video.currentTime = 0;
                    video.play().catch(e => console.log('Preview play failed:', e));
                }
            }, 500);
        });
        
        card.addEventListener('mouseleave', () => {
            clearTimeout(hoverTimeout);
            if (video && video.tagName === 'VIDEO') {
                video.pause();
                video.currentTime = 0;
            }
        });
    });
}

function initVideoPlayer() {
    const videoPlayer = document.getElementById('videoPlayer');
    if (!videoPlayer) return;
    
    // Auto-play on page load
    videoPlayer.play().catch(e => {
        console.log('Auto-play failed:', e);
        // Show play button if autoplay fails
        videoPlayer.controls = true;
    });
    
    // Update view count (simulated)
    setTimeout(() => {
        const viewsElement = document.querySelector('.video-views-date span');
        if (viewsElement) {
            let currentViews = viewsElement.textContent;
            let viewCount = parseInt(currentViews.replace(/[^0-9]/g, ''));
            viewCount += 1;
            viewsElement.textContent = `${viewCount}K views`;
        }
    }, 3000);
}

function initCommentInteractions() {
    // Comment input focus
    const commentInput = document.querySelector('.comment-input');
    if (commentInput) {
        commentInput.addEventListener('focus', () => {
            commentInput.style.borderBottomWidth = '2px';
        });
        
        commentInput.addEventListener('blur', () => {
            if (!commentInput.value) {
                commentInput.style.borderBottomWidth = '1px';
            }
        });
    }
    
    // Like/Dislike buttons
    const actionButtons = document.querySelectorAll('.action-button');
    actionButtons.forEach(button => {
        button.addEventListener('click', () => {
            if (button.querySelector('.material-icons').textContent === 'thumb_up') {
                button.style.color = '#065fd4';
            }
        });
    });
}

function initSearch() {
    const searchForm = document.querySelector('.search-bar');
    const searchInput = document.querySelector('.search-input');
    
    if (searchForm && searchInput) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const searchTerm = searchInput.value.trim();
            if (searchTerm) {
                // Filter videos based on search term
                filterVideos(searchTerm);
            }
        });
    }
}

function filterVideos(searchTerm) {
    const videoCards = document.querySelectorAll('.video-card');
    const lowerSearchTerm = searchTerm.toLowerCase();
    
    videoCards.forEach(card => {
        const title = card.querySelector('.video-title').textContent.toLowerCase();
        const channel = card.querySelector('.channel-name').textContent.toLowerCase();
        
        if (title.includes(lowerSearchTerm) || channel.includes(lowerSearchTerm)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

function initSidebarToggle() {
    const menuButton = document.querySelector('.menu-button');
    const sidebar = document.querySelector('.sidebar');
    const content = document.querySelector('.content');
    
    if (menuButton && sidebar && content) {
        menuButton.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            if (sidebar.classList.contains('collapsed')) {
                sidebar.style.width = '72px';
                content.style.marginLeft = '72px';
                content.style.width = 'calc(100% - 72px)';
            } else {
                sidebar.style.width = '240px';
                content.style.marginLeft = '240px';
                content.style.width = 'calc(100% - 240px)';
            }
        });
    }
}

// Chip filtering
document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
        // Remove active class from all chips
        document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        // Add active class to clicked chip
        chip.classList.add('active');
        
        // Filter logic based on chip text
        const filterText = chip.textContent.toLowerCase();
        if (filterText === 'all') {
            document.querySelectorAll('.video-card').forEach(card => {
                card.style.display = '';
            });
        } else if (filterText === 'shorts') {
            document.querySelectorAll('.video-card').forEach(card => {
                const duration = card.querySelector('.video-duration').textContent;
                if (duration === '0:30' || duration.includes(':3') || duration.includes(':2')) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        }
    });
});

// Show more description
const showMore = document.querySelector('.show-more');
if (showMore) {
    showMore.addEventListener('click', () => {
        const description = document.querySelector('.video-description');
        description.style.maxHeight = 'none';
        showMore.style.display = 'none';
    });
}
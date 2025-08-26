#!/bin/bash
# Template 91 실시간 로그 모니터링 스크립트

echo "=== Template 91 실시간 로그 모니터링 ==="
echo "종료하려면 Ctrl+C를 누르세요"
echo ""

tail -f logs/clipping_api.log | grep --line-buffered -E "template_91|Template 91|TemplateVideoEncoder|_apply_continuous|Bookmarked|Creating template1|북마크|클립 생성|FFmpeg|merge_clips" | while read line; do
    if echo "$line" | grep -q "=== Template 91 processing started"; then
        echo -e "\n\033[1;32m$line\033[0m"  # 녹색 굵게
    elif echo "$line" | grep -q "Template 91 클리핑 완료"; then
        echo -e "\033[1;36m$line\033[0m"  # 청록색 굵게
    elif echo "$line" | grep -q "ERROR"; then
        echo -e "\033[1;31m$line\033[0m"  # 빨간색 굵게
    elif echo "$line" | grep -q "Bookmarked indices"; then
        echo -e "\033[1;33m$line\033[0m"  # 노란색 굵게
    elif echo "$line" | grep -q "Creating.*clip"; then
        echo -e "\033[1;35m$line\033[0m"  # 보라색 굵게
    else
        echo "$line"
    fi
done
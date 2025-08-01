# Production Deployment Guide

## 서버 요구사항

- Ubuntu 20.04+ or CentOS 8+
- Python 3.8+
- FFmpeg 4.0+
- Redis (선택사항, 분산 환경용)
- 최소 4GB RAM
- 충분한 디스크 공간 (비디오 처리용)

## 설치 단계

### 1. 시스템 패키지 설치

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg redis-server nginx

# CentOS/RHEL
sudo yum install -y python3-pip python3-venv ffmpeg redis nginx
```

### 2. 애플리케이션 설치

```bash
# 애플리케이션 디렉토리로 이동
cd /opt
sudo git clone https://github.com/yourusername/shadowing_maker_xls.git clipping-api
cd clipping-api

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경 설정
sudo cp .env.example .env
sudo nano .env  # 환경에 맞게 수정
```

### 3. 디렉토리 권한 설정

```bash
# 필요한 디렉토리 생성
sudo mkdir -p /var/lib/clipping-api/output
sudo mkdir -p /var/log/clipping-api

# 권한 설정
sudo chown -R www-data:www-data /var/lib/clipping-api
sudo chown -R www-data:www-data /var/log/clipping-api
sudo chown -R www-data:www-data /opt/clipping-api
```

### 4. Systemd 서비스 설정

```bash
# 서비스 파일 복사
sudo cp clipping-api.service /etc/systemd/system/

# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable clipping-api
sudo systemctl start clipping-api

# 상태 확인
sudo systemctl status clipping-api
```

### 5. Nginx 리버스 프록시 설정

```nginx
# /etc/nginx/sites-available/clipping-api
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

```bash
# 사이트 활성화
sudo ln -s /etc/nginx/sites-available/clipping-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. SSL 설정 (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 환경 변수 설정

`.env` 파일에서 다음 설정들을 환경에 맞게 수정:

```bash
# 서버 설정
HOST=0.0.0.0
PORT=8080
WORKERS=4  # CPU 코어 수에 맞게 조정

# Redis (선택사항)
REDIS_HOST=localhost
REDIS_PORT=6379

# 디렉토리 설정
OUTPUT_DIR=/var/lib/clipping-api/output
ADDITIONAL_MEDIA_ROOTS=/mnt/qnap/media_eng/indexed_media:/mnt/qnap/media_kor

# 보안
ALLOWED_ORIGINS=https://your-domain.com

# 성능
MAX_WORKERS=4  # 동시 비디오 처리 작업 수
```

## 모니터링

### 로그 확인

```bash
# 서비스 로그
sudo journalctl -u clipping-api -f

# 애플리케이션 로그
tail -f /var/log/clipping-api/error.log
tail -f /var/log/clipping-api/access.log
```

### 성능 모니터링

```bash
# CPU 및 메모리 사용량
htop

# 디스크 사용량
df -h /var/lib/clipping-api
```

## 백업

### 자동 백업 스크립트

```bash
#!/bin/bash
# /opt/clipping-api/backup.sh

BACKUP_DIR="/backup/clipping-api"
DATE=$(date +%Y%m%d_%H%M%S)

# 메타데이터 백업
tar -czf "$BACKUP_DIR/metadata_$DATE.tar.gz" /var/lib/clipping-api/output/*/metadata.json

# 오래된 백업 삭제 (30일 이상)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

### Cron 설정

```bash
# 매일 새벽 3시 백업
0 3 * * * /opt/clipping-api/backup.sh
```

## 문제 해결

### 서비스가 시작되지 않을 때

1. 로그 확인: `sudo journalctl -u clipping-api -n 50`
2. 권한 확인: 모든 디렉토리가 www-data 소유인지 확인
3. FFmpeg 설치 확인: `ffmpeg -version`

### 메모리 부족

1. 스왑 파일 추가
2. WORKERS 수 감소
3. 동시 처리 작업 수 제한 (MAX_WORKERS)

### 디스크 공간 부족

1. 오래된 출력 파일 정기적으로 삭제
2. 자동 정리 기능 활성화 (24시간 후 자동 삭제)

## 업데이트

```bash
cd /opt/clipping-api
sudo systemctl stop clipping-api
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start clipping-api
```

## 보안 권장사항

1. 방화벽 설정으로 필요한 포트만 개방
2. ALLOWED_ORIGINS 설정으로 CORS 제한
3. 미디어 파일 접근 경로 제한 (ALLOWED_MEDIA_ROOTS)
4. 정기적인 시스템 업데이트
5. HTTPS 사용 필수
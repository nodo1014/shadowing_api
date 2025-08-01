#!/bin/bash

case "$1" in
    start)
        echo "Starting Video Clipping API..."
        # Kill existing processes
        pkill -f "gunicorn.*clipping_api" 2>/dev/null || true
        sleep 2
        
        # Create logs directory
        mkdir -p logs
        
        # Start server in background
        nohup /home/kang/.local/bin/gunicorn clipping_api:app \
            --workers 4 \
            --worker-class uvicorn.workers.UvicornWorker \
            --bind 0.0.0.0:8080 \
            --access-logfile logs/access.log \
            --error-logfile logs/error.log \
            --log-level info \
            --timeout 300 \
            --graceful-timeout 60 \
            --max-requests 1000 \
            --max-requests-jitter 50 \
            --daemon &
        
        echo "Server started in background."
        ;;
    stop)
        echo "Stopping Video Clipping API..."
        pkill -f "gunicorn.*clipping_api"
        echo "Server stopped."
        ;;
    restart)
        echo "Restarting Video Clipping API..."
        $0 stop
        sleep 3
        $0 start
        ;;
    status)
        if pgrep -f "gunicorn.*clipping_api" > /dev/null; then
            echo "✅ Server is running"
            echo "Processes:"
            ps aux | grep "gunicorn.*clipping_api" | grep -v grep
            echo ""
            echo "Testing API connection..."
            if curl -s http://localhost:8080/docs > /dev/null; then
                echo "✅ API responding normally"
            else
                echo "❌ API not responding"
            fi
        else
            echo "❌ Server is not running"
        fi
        ;;
    logs)
        echo "=== Error Log ==="
        tail -n 20 logs/error.log
        echo ""
        echo "=== Access Log ==="
        tail -n 10 logs/access.log
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the server in background"
        echo "  stop    - Stop the server"
        echo "  restart - Restart the server"
        echo "  status  - Check server status"
        echo "  logs    - Show recent logs"
        exit 1
        ;;
esac
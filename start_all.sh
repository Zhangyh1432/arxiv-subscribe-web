#!/bin/bash

# 获取脚本所在的绝对路径,也就是项目根目录
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "🚀 Starting all services for arXiv Subscribe Web..."
echo "三个新的终端窗口即将打开,分别用于 PDF 解析、后端和前端。"
echo "请确保您已经根据 README 完成了所有依赖的安装。"

#
# 使用 Heredoc 将 AppleScript 命令传递给 osascript
# 这是处理复杂引号和命令的最可靠方法
#

# 1. 启动 miner-u PDF 解析服务
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '${PROJECT_DIR}'; echo '--- ❶ PDF Parser (miner-u) ---'; conda activate mineru; mineru-api --host 0.0.0.0 --port 8000"
end tell
EOF

# 给予一点时间让上一个窗口启动
sleep 2

# 2. 启动后端 Flask 服务器
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '${PROJECT_DIR}'; echo '--- ❷ Backend Server (Flask) ---'; conda activate arxiv-subscribe; python backend/app.py"
end tell
EOF

# 给予一点时间
sleep 2

# 3. 启动前端 React 服务器
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '${PROJECT_DIR}/frontend'; echo '--- ❸ Frontend Server (React) ---'; npm start"
end tell
EOF


echo "✅ All services have been launched in new terminal windows."
echo "要停止整个应用,请手动关闭那三个新打开的终端窗口。"
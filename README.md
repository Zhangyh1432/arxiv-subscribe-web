# arXiv AI 订阅与深度分析服务

这是一个功能强大的Web应用，旨在将您的arXiv论文阅读体验提升到一个新的水平。它不仅仅是一个简单的订阅工具，更是一个集成了AI翻译与深度分析的**交互式研究助手**。

通过简洁的Web界面，您可以根据自定义的日期范围、分类和关键词，精确地获取您感兴趣的论文。应用提供了两种强大的工作流：

1.  **即时在线分析**: 对于任意单篇论文，您可以触发即时全文深度分析。应用会立刻跳转到专属结果页面，实时展示分析进度，并在完成后直接在线呈现完整的分析报告。您也可以在该页面将结果一键发送到邮箱。
2.  **批量离线处理**: 您可以一次性勾选多篇论文，触发批量分析。应用会在后台为您处理所有请求，并将所有结果打包成一个zip文件发送到您的邮箱。

此外，所有成功分析过的论文都会被**自动缓存**。当您再次请求分析同一篇论文时，应用会直接从本地 (`backend/data/analysis_results/`) 读取并展示结果，极大地节省了时间和资源。

---

## 🚀 一键启动 (macOS 用户)

在完成下面的“安装与配置”步骤后，您可以使用一键启动脚本来运行整个应用。

1.  **赋予脚本执行权限 (仅需首次)**
    ```bash
    chmod +x start_all.sh
    ```

2.  **启动所有服务**
    ```bash
    ./start_all.sh
    ```
    该脚本会自动打开三个新的终端窗口，并分别在其中启动 PDF 解析服务 (`mineru` 环境)、后端服务 (`arxiv-subscribe` 环境)和前端服务。要关闭应用，只需手动关闭这三个终端窗口即可。

---

## ⚙️ 安装与配置 (所有用户)

### 先决条件

- [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)
- [Node.js 和 npm](https://nodejs.org/en/download/)

### 第一步：安装 PDF 解析服务 (miner-u)

此服务需要一个独立的 Conda 环境。

```bash
# (如果已有 mineru 环境, 请直接激活: conda activate mineru)
conda create --name mineru python=3.9 -y
conda activate mineru

# 安装 miner-u
pip install "miner-u[all]"
```

### 第二步：设置项目后端

此项目后端也需要一个独立的 Conda 环境。

1.  **进入后端目录并创建环境 (在项目根目录执行)**
    ```bash
    cd backend
    
    # 创建并激活环境
    conda create --name arxiv-subscribe python=3.9 -y
    conda activate arxiv-subscribe
    
    # 安装项目Python依赖
    pip install -r requirements.txt
    ```

2.  **配置环境变量**
    ```bash
    # 确保仍在 backend 目录下
    cp .env.example .env 
    ```
    - 打开 `backend/.env` 文件，填入您的**邮箱授权码**、**DashScope API密钥**、**收件人邮箱**等信息。
    - 确保 `PDF_PARSER_URL` 的值 (默认为 `http://127.0.0.1:8000/file_parse`) 与 `miner-u` 服务地址匹配。

### 第三步：设置项目前端

1.  **安装依赖 (在项目根目录执行)**
    ```bash
    cd frontend
    npm install
    ```

---

## 🛠️ 手动启动 (用于调试或非macOS用户)

您需要**同时启动PDF解析服务、后端和前端**。请打开三个独立的终端窗口。

1.  **终端 1: 启动PDF解析服务**
    ```bash
    # 激活 miner-u 环境
    conda activate mineru
    
    # 启动 miner-u API 服务
    mineru-api --host 0.0.0.0 --port 8000
    ```

2.  **终端 2: 启动后端服务**
    ```bash
    # 激活项目后端环境
    conda activate arxiv-subscribe
    
    # 运行Flask应用 (在项目根目录)
    python backend/app.py
    ```

3.  **终端 3: 启动前端服务**
    ```bash
    # 进入前端目录
    cd frontend
    
    # 启动React应用
    npm start
    ```
    这会自动在您的浏览器中打开 `http://localhost:3000`。

---

## 💡 如何使用

1.  在浏览器中打开 `http://localhost:3000`。
2.  在**查询页面**，设置查询条件，点击“Fetch Papers for Review”。
3.  在**结果审核页面**，您可以进行两种操作：
    - **单篇在线分析**:
        - 点击任意论文卡片上的 **Translate** 按钮，可以快速翻译标题和摘要。
        - 点击 **Analyze** 按钮，页面会立刻跳转到该论文的专属分析页面。
        - 页面会显示“分析中”的实时状态，分析完成后会自动展示结果。
        - 在该页面，您可以直接阅读报告，或输入邮箱将报告发送给自己。
    - **批量离线处理**:
        - **勾选**多篇您感兴趣的论文。
        - 在页面顶部的操作栏中，输入您的邮箱（可选，若不填则使用默认配置），然后点击 **Analyze & Email Selected** 按钮。
        - 后台任务开始后，您可以在页面顶部的状态栏看到实时进度。
        - 任务完成后，去您的邮箱查收包含所有分析报告的zip压缩包。

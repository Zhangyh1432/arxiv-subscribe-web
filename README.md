# arXiv AI 订阅与深度分析服务

这是一个功能强大的Web应用，旨在将您的arXiv论文阅读体验提升到一个新的水平。它不仅仅是一个简单的订阅工具，更是一个集成了AI翻译与深度分析的**交互式研究助手**。

通过简洁的Web界面，您可以根据自定义的日期范围、分类和关键词，精确地获取您感兴趣的论文。所有分析过的论文都会被自动缓存，方便您随时回顾。

---

## ✨ 功能亮点

*   **分析仓库与搜索**: 提供一个独立的“仓库”页面，集中展示所有分析过的论文历史。您可以通过论文标题或ID进行快速搜索，轻松找到历史记录。
*   **近期查阅历史**: 首页会展示您最近分析过的10篇论文，方便您快速访问和回顾。
*   **分类预设组**: 在查询页面提供可点击的分类预设按钮（如“机器学习论文分类组”），一键选择多个相关分类，简化操作。您可以通过直接编辑 `frontend/src/category-presets.json` 文件来**自定义这些预设组**。
*   **数学公式渲染**: 分析报告页面现已支持 **LaTeX**，可以正确渲染复杂的数学公式。
*   **优化的交互体验**: 获取论文列表、分析单篇论文等耗时操作现在都会在**新的浏览器标签页**中打开，不会打断您在当前页面的操作。
*   **缓存管理**: 首页提供“清除缓存”按钮，方便您在更新了分析模型或Prompt后，对所有论文进行重新分析。

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
2.  **安装数学公式渲染依赖**
    ```bash
    # 仍在 frontend 目录下
    npm install remark-math rehype-katex katex
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
2.  在**查询页面**，您可以通过顶部的**分类预设组**（如“机器学习论文分类组”）或下方的复选框来选择分类，然后输入关键词，点击“Fetch Papers & Open Results”。
3.  后台开始获取论文后，页面顶部的状态栏会显示实时进度。完成后，状态栏会出现一个**“View Results”按钮**。
4.  点击“View Results”按钮，**新的标签页**会打开，显示获取到的论文列表以供审核。
5.  在**结果审核页面**，您可以进行两种操作：
    - **单篇在线分析**:
        - 点击任意论文卡片上的 **Translate** 按钮，可以快速翻译标题和摘要。
        - 点击 **Analyze** 按钮，会在新的标签页中打开该论文的专属分析页面。
        - 页面会显示“分析中”的实时状态，分析完成后会自动展示包含**数学公式**的完整报告。
    - **批量离线处理**:
        - **勾选**多篇您感兴趣的论文。
        - 在页面顶部的操作栏中，输入您的邮箱（可选），然后点击 **Analyze & Email Selected** 按钮。
        - 后台任务开始后，您可以在首页的状态栏看到实时进度。
        - 任务完成后，去您的邮箱查收包含所有分析报告的zip压缩包。
6.  在任何时候，您都可以通过首页的**“近期查阅”**列表或**“分析仓库”**页面，来查找和回顾您分析过的所有论文。
import os
import re
import json
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from pypdf import PdfReader

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DB_FILE = "paper_database.json"

# ----------------------
# 加载文献库
# ----------------------
def load_papers():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

# ----------------------
# 从上传的 PDF 提取标题
# ----------------------
def extract_title_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        info = reader.metadata
        title = info.title if info and info.title else None

        # 元数据没有就从第一页文本猜
        if not title and len(reader.pages) > 0:
            text = reader.pages[0].extract_text()[:3000].strip()
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for line in lines[:15]:
                if len(line) > 15 and not line.lower().startswith(('abstract', 'keywords', 'introduction', 'http', 'www', 'doi')):
                    title = line
                    break
        return title or "无法识别标题"
    except Exception as e:
        return None

# ----------------------
# 从PDF提取完整信息
# ----------------------
def extract_info_from_pdf(pdf_path, filename):
    try:
        reader = PdfReader(pdf_path)
        info = reader.metadata

        title = info.title if info and info.title else None
        author = info.author if info and info.author else None

        # 从文件名提取年份
        year_match = re.search(r'(20\d{2})', filename)
        year = year_match.group(1) if year_match else "未知"

        # 如果元数据没有标题，从第一页文本提取
        if not title and len(reader.pages) > 0:
            text = reader.pages[0].extract_text()[:3000].strip()
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for line in lines[:15]:
                if len(line) > 15 and not line.lower().startswith(('abstract', 'keywords', 'introduction', 'http', 'www', 'doi')):
                    title = line
                    break

        # 如果没有作者，尝试从文件名提取
        if not author:
            author_match = re.match(r'^[\d\s]*([A-Za-z\u4e00-\u9fff]+)', filename)
            if author_match:
                author = author_match.group(1)
            else:
                author = "未知"

        return {
            "title": title or filename.replace('.pdf', ''),
            "author": author,
            "year": year,
            "filename": filename
        }
    except Exception as e:
        return None

# ----------------------
# 查重逻辑（模糊匹配）
# ----------------------
def is_duplicate(new_title, paper_list, threshold=65):
    if not new_title:
        return False, None
    new_clean = re.sub(r'[^\w]', '', new_title.lower()).strip()
    for paper in paper_list:
        p_title = paper["title"]
        p_clean = re.sub(r'[^\w]', '', p_title.lower()).strip()
        # 包含匹配
        if new_clean in p_clean or p_clean in new_clean:
            return True, paper
        # 相似度匹配
        common = set(new_clean) & set(p_clean)
        rate = len(common) / max(len(new_clean), len(p_clean)) * 100
        if rate >= threshold:
            return True, paper
    return False, None

# ----------------------
# 网页界面
# ----------------------
@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>组会文献查重系统</title>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box}
body{
    max-width:950px;
    margin:0 auto;
    font-family:'Nunito',-apple-system,sans-serif;
    padding:30px 20px;
    background:linear-gradient(135deg,#fce4ec 0%,#e3f2fd 100%);
    min-height:100vh
}
.header{
    text-align:center;
    margin-bottom:30px
}
.header h1{
    color:#e91e63;
    font-size:2.2em;
    margin:0;
    display:flex;
    align-items:center;
    justify-content:center;
    gap:10px
}
.header p{
    color:#666;
    margin-top:8px;
    font-size:1.1em
}
.count-badge{
    display:inline-block;
    background:linear-gradient(135deg,#e91e63,#f48fb1);
    color:white;
    padding:8px 20px;
    border-radius:50px;
    font-weight:700;
    margin-top:15px;
    box-shadow:0 4px 15px rgba(233,30,99,0.3)
}
.upload-section{
    background:white;
    border-radius:20px;
    padding:35px;
    margin:25px 0;
    box-shadow:0 10px 40px rgba(0,0,0,0.1);
    text-align:center
}
.upload-area{
    border:3px dashed #f48fb1;
    padding:40px;
    border-radius:15px;
    background:#fce4ec20;
    transition:all 0.3s
}
.upload-area:hover{
    border-color:#e91e63;
    background:#fce4ec40
}
.upload-icon{
    font-size:50px;
    margin-bottom:15px
}
.file-input{
    display:none
}
.file-label{
    display:inline-block;
    padding:12px 30px;
    background:linear-gradient(135deg,#e91e63,#f48fb1);
    color:white;
    border-radius:50px;
    cursor:pointer;
    font-weight:600;
    transition:transform 0.2s,box-shadow 0.2s;
    box-shadow:0 4px 15px rgba(233,30,99,0.3)
}
.file-label:hover{
    transform:translateY(-2px);
    box-shadow:0 6px 20px rgba(233,30,99,0.4)
}
.file-name{
    margin-top:15px;
    color:#666;
    font-size:0.95em
}
.check-btn{
    margin-top:20px;
    padding:14px 40px;
    background:linear-gradient(135deg,#7c4dff,#b388ff);
    color:white;
    border:none;
    border-radius:50px;
    cursor:pointer;
    font-weight:700;
    font-size:1.1em;
    transition:transform 0.2s,box-shadow 0.2s;
    box-shadow:0 4px 15px rgba(124,77,255,0.3)
}
.check-btn:hover{
    transform:translateY(-2px);
    box-shadow:0 6px 20px rgba(124,77,255,0.4)
}
.result-box{
    margin-top:25px;
    padding:25px;
    border-radius:15px;
    display:none;
    animation:popIn 0.3s ease
}
@keyframes popIn{
    from{opacity:0;transform:scale(0.95)}
    to{opacity:1;transform:scale(1)}
}
.result-duplicate{
    background:linear-gradient(135deg,#ffebee,#ffcdd2);
    border-left:5px solid #e53935
}
.result-new{
    background:linear-gradient(135deg,#e8f5e9,#c8e6c9);
    border-left:5px solid #43a047
}
.result-title{
    font-size:1.2em;
    font-weight:700;
    margin-bottom:15px
}
.result-content{
    color:#555;
    line-height:1.8
}
.paper-match{
    background:white;
    padding:15px;
    border-radius:10px;
    margin-top:15px;
    box-shadow:0 2px 10px rgba(0,0,0,0.05)
}
.add-btn{
    margin-top:15px;
    padding:12px 35px;
    background:linear-gradient(135deg,#00c853,#69f0ae);
    color:white;
    border:none;
    border-radius:50px;
    cursor:pointer;
    font-weight:700;
    transition:transform 0.2s,box-shadow 0.2s;
    box-shadow:0 4px 15px rgba(0,200,83,0.3)
}
.add-btn:hover{
    transform:translateY(-2px);
    box-shadow:0 6px 20px rgba(0,200,83,0.4)
}
.paper-list-section{
    margin-top:40px;
    background:white;
    border-radius:20px;
    padding:30px;
    box-shadow:0 10px 40px rgba(0,0,0,0.1)
}
.paper-list-header{
    display:flex;
    align-items:center;
    gap:10px;
    margin-bottom:20px
}
.paper-list-header h2{
    color:#e91e63;
    margin:0;
    font-size:1.5em
}
.search-input{
    width:100%;
    max-width:400px;
    padding:12px 20px;
    border:2px solid #fce4ec;
    border-radius:50px;
    font-size:1em;
    transition:border-color 0.3s;
    margin-bottom:20px
}
.search-input:focus{
    outline:none;
    border-color:#e91e63
}
.paper-item{
    background:linear-gradient(135deg,#fce4ec10,#e3f2fd10);
    padding:15px 20px;
    margin:12px 0;
    border-radius:12px;
    border-left:4px solid #e91e63;
    transition:transform 0.2s,box-shadow 0.2s
}
.paper-item:hover{
    transform:translateX(5px);
    box-shadow:0 4px 15px rgba(233,30,99,0.1)
}
.paper-title{
    font-weight:700;
    color:#333;
    font-size:1.05em
}
.paper-meta{
    color:#888;
    font-size:0.9em;
    margin-top:6px
}
.empty-msg{
    text-align:center;
    color:#aaa;
    padding:30px
}
.loading{
    text-align:center;
    padding:20px;
    color:#e91e63
}
</style>
</head>
<body>
<div class="header">
    <h1><span>📚</span> 组会文献查重系统</h1>
    <p>上传PDF，一键查重，告别重复分享</p>
    <div class="count-badge">已收录 <span id="count">...</span> 篇文献</div>
</div>

<div class="upload-section">
    <div class="upload-area">
        <div class="upload-icon">📄</div>
        <input type="file" id="pdfFile" class="file-input" accept=".pdf">
        <label for="pdfFile" class="file-label">选择PDF文件</label>
        <div class="file-name" id="fileName">未选择文件</div>
    </div>
    <button class="check-btn" onclick="uploadAndCheck()">上传并查重</button>
</div>

<div id="result" class="result-box"></div>

<div class="paper-list-section">
    <div class="paper-list-header">
        <h2>📖 已分享文献汇总</h2>
    </div>
    <input type="text" id="searchInput" class="search-input" placeholder="搜索标题、作者或年份..." oninput="filterPapers()">
    <div id="paperList" class="loading">加载中...</div>
</div>

<script>
let allPapers = [];
let lastCheckData = null;

document.getElementById('pdfFile').addEventListener('change', function(e){
    let name = e.target.files[0] ? e.target.files[0].name : '未选择文件';
    document.getElementById('fileName').textContent = name;
});

async function loadCount(){
    let r = await fetch('/count');
    let d = await r.json();
    document.getElementById('count').textContent = d.count;
}

async function loadPapers(){
    let r = await fetch('/papers');
    allPapers = await r.json();
    renderPapers(allPapers);
}

function renderPapers(papers){
    let html = '';
    if(papers.length === 0){
        html = '<div class="empty-msg">暂无文献记录</div>';
    } else {
        papers.forEach((p, i) => {
            html += `<div class="paper-item">
                <div class="paper-title">${i+1}. ${p.title}</div>
                <div class="paper-meta">作者：${p.author} | 年份：${p.year}</div>
            </div>`;
        });
    }
    document.getElementById('paperList').innerHTML = html;
}

function filterPapers(){
    let keyword = document.getElementById('searchInput').value.toLowerCase();
    let filtered = allPapers.filter(p =>
        p.title.toLowerCase().includes(keyword) ||
        p.author.toLowerCase().includes(keyword) ||
        p.year.includes(keyword)
    );
    renderPapers(filtered);
}

async function uploadAndCheck(){
    let file = document.getElementById('pdfFile').files[0];
    if(!file){alert('请先选择PDF文件');return}
    let form = new FormData();
    form.append('pdf', file);

    let dom = document.getElementById('result');
    dom.className = 'result-box';
    dom.style.display = 'block';
    dom.innerHTML = '<div class="loading">正在查重中...</div>';

    let res = await fetch('/upload-check', {method:'POST', body:form});
    let data = await res.json();
    lastCheckData = data;

    if(data.duplicate){
        dom.className = 'result-box result-duplicate';
        dom.innerHTML = `
            <div class="result-title">❌ 这篇文献已经分享过啦</div>
            <div class="result-content">
                <strong>识别标题：</strong>${data.title}
                <div class="paper-match">
                    <strong>已存在记录：</strong><br>
                    ${data.paper.title}<br>
                    <small>作者：${data.paper.author} | 年份：${data.paper.year}</small>
                </div>
            </div>`;
    } else {
        dom.className = 'result-box result-new';
        dom.innerHTML = `
            <div class="result-title">✅ 这是一篇新文献，可以分享</div>
            <div class="result-content">
                <strong>识别标题：</strong>${data.title}
                <br><br>
                <button class="add-btn" onclick="addToDatabase()">添加到数据库</button>
            </div>`;
    }
}

async function addToDatabase(){
    if(!lastCheckData || !lastCheckData.full_info){
        alert('请先上传并查重');
        return;
    }

    let res = await fetch('/add-paper', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(lastCheckData.full_info)
    });
    let data = await res.json();

    if(data.success){
        let dom = document.getElementById('result');
        dom.innerHTML = '<div class="result-title">🎉 已成功添加到数据库</div>';
        loadCount();
        loadPapers();
        lastCheckData = null;
    } else {
        alert('添加失败：' + (data.error || '未知错误'));
    }
}

loadCount();
loadPapers();
</script>
</body>
</html>
'''

# ----------------------
# 接口：文献数量
# ----------------------
@app.route('/count')
def count():
    return jsonify(count=len(load_papers()))

# ----------------------
# 接口：文献列表
# ----------------------
@app.route('/papers')
def papers():
    return jsonify(load_papers())

# ----------------------
# 核心：上传PDF + 查重
# ----------------------
@app.route('/upload-check', methods=['POST'])
def upload_check():
    if 'pdf' not in request.files:
        return jsonify({"error": "no file"}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({"error": "no selected file"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)

    title = extract_title_from_pdf(path)
    papers = load_papers()
    dup, paper = is_duplicate(title, papers)

    # 提取完整信息用于可能的添加
    full_info = extract_info_from_pdf(path, filename)

    os.remove(path)  # 上传后删除，不占空间

    return jsonify({
        "title": title,
        "duplicate": dup,
        "paper": paper,
        "full_info": full_info
    })

# ----------------------
# 接口：添加文献到数据库
# ----------------------
@app.route('/add-paper', methods=['POST'])
def add_paper():
    data = request.json
    if not data or 'title' not in data:
        return jsonify({"error": "missing data"}), 400

    papers = load_papers()

    # 检查是否已存在
    dup, _ = is_duplicate(data['title'], papers)
    if dup:
        return jsonify({"error": "already exists"}), 400

    # 添加新文献
    new_paper = {
        "title": data.get('title', '未知'),
        "author": data.get('author', '未知'),
        "year": data.get('year', '未知'),
        "filename": data.get('filename', '')
    }
    papers.append(new_paper)

    # 保存到文件
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    return jsonify({"success": True, "paper": new_paper})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("文献查重系统已启动")
    app.run(host='0.0.0.0', port=port)

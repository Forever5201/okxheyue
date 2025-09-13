"""
Local MCP（本地守护进程）设计说明 + PoC 实现 (FastAPI)

目的：
- 在本地运行一个受控服务（MCP，可信管家），允许 AI 按需读取你事先授权的 K 线文件。
- 保证最小权限（白名单）、只读、可审计、原子更新、不随意上传数据。

特性要点（白话）：
1. manifest.json：列出被授权允许读取的文件（由管理员通过 /authorize 添加）。
2. MCP 服务：对外提供接口：/list_allowed_files, /authorize, /deauthorize, /get_kline, /read_tail, /audit。
3. 每次读取写审计（audit.log），包含时间、操作、文件、返回行数等元数据。
4. 接口鉴权：使用本地环境变量 MCP_API_KEY 作为简易 API Key 验证（生产建议更严）。
5. 原子写入：保存 manifest 时使用临时文件 + 原子替换，避免读到半写文件。

运行前准备：
- Python 3.9+
- 安装依赖：pip install fastapi uvicorn pandas pyarrow
- 设置环境变量：export MCP_API_KEY=你的密钥
- 数据目录：在代码同级目录下创建 data_kline 目录，并放入 CSV/Parquet 文件，例如 BTC_1h.csv

运行：
uvicorn mcp_fastapi:app --host 127.0.0.1 --port 8000

安全提示（必须认真对待）：
- 目前 PoC 通过 API Key 做鉴权，但部署时应加本地防火墙或进程隔离，审计日志应周期性备份与签名。
- 默认禁止任何写/执行行为，仅允许读取 manifest 中白名单里的文件。

下面是可直接运行的代码：
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional
import os, json, datetime
import pandas as pd

# -------------------- 配置 --------------------
DATA_ROOT = os.path.abspath("./data_kline")
MANIFEST_PATH = os.path.join(DATA_ROOT, "manifest.json")
AUDIT_LOG_PATH = os.path.join(DATA_ROOT, "audit.log")
# API Key 从环境变量读取
ENV_API_KEY_NAME = "MCP_API_KEY"
# 可配置最大返回行数上限（防止一次性返回太多）
MAX_BARS_LIMIT = 5000

# -------------------- FastAPI 实例 --------------------
app = FastAPI(title="Local MCP (PoC)")

# -------------------- 工具函数 --------------------

def ensure_dirs():
    os.makedirs(DATA_ROOT, exist_ok=True)
    if not os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump({"files": []}, f, ensure_ascii=False, indent=2)


def load_manifest():
    ensure_dirs()
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest: dict):
    """原子性写入 manifest：写 tmp 文件并 replace。"""
    ensure_dirs()
    tmp = MANIFEST_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    # 原子替换
    os.replace(tmp, MANIFEST_PATH)


def append_audit(entry: dict):
    """把一条审计记录追加写入 audit.log（每行为一个 JSON）。"""
    ensure_dirs()
    entry = dict(entry)  # 复制一份
    entry["ts"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def is_allowed(filename: str) -> bool:
    manifest = load_manifest()
    return filename in manifest.get("files", [])


def safe_join(name: str) -> str:
    """基础安全检查：禁止路径穿越与绝对路径。返回绝对路径。"""
    if not name or ".." in name or name.startswith("/"):
        raise HTTPException(status_code=400, detail="invalid filename")
    full = os.path.join(DATA_ROOT, name)
    full = os.path.abspath(full)
    # 确保目标仍在 DATA_ROOT 下
    if not full.startswith(os.path.abspath(DATA_ROOT) + os.sep) and full != os.path.abspath(DATA_ROOT):
        raise HTTPException(status_code=400, detail="invalid filename")
    return full


def file_fingerprint(path: str) -> str:
    """轻量文件指纹：mtime_ns + size，便于审计对比。"""
    st = os.stat(path)
    return f"{st.st_mtime_ns}-{st.st_size}"

# -------------------- 简单鉴权依赖 --------------------

def get_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """从 header 获取 API Key，并与环境变量比较。生产请使用更严格的鉴权方式。"""
    key = os.environ.get(ENV_API_KEY_NAME)
    if not key:
        raise HTTPException(status_code=500, detail=f"Server misconfigured: set {ENV_API_KEY_NAME} env var")
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Missing API key header 'x-api-key'")
    if x_api_key != key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# -------------------- 请求/响应模型 --------------------

class AuthorizeReq(BaseModel):
    files: List[str]

class DeauthorizeReq(BaseModel):
    files: List[str]

class KlineReq(BaseModel):
    name: str
    start: Optional[str] = None
    end: Optional[str] = None
    max_bars: Optional[int] = 500

# -------------------- API 实现 --------------------

@app.on_event("startup")
def startup_event():
    ensure_dirs()


@app.get("/list_allowed_files")
def list_allowed_files(api_key: str = Depends(get_api_key)):
    """返回 manifest 中的白名单文件列表。"""
    return load_manifest()


@app.post("/authorize")
def authorize(req: AuthorizeReq, api_key: str = Depends(get_api_key)):
    """把文件加入白名单（管理员操作）。
    注意：本 PoC 没有细粒度管理员身份区分，实际部署应限制此接口。"""
    manifest = load_manifest()
    files = set(manifest.get("files", []))
    added = []
    for f in req.files:
        # 检查路径安全性
        if ".." in f or f.startswith("/"):
            raise HTTPException(status_code=400, detail=f"invalid filename: {f}")
        full = os.path.join(DATA_ROOT, f)
        if not os.path.exists(full):
            raise HTTPException(status_code=404, detail=f"file not found: {f}")
        if f not in files:
            files.add(f)
            added.append(f)
    manifest["files"] = sorted(list(files))
    save_manifest(manifest)
    append_audit({"action": "authorize", "added": added, "by": api_key})
    return {"status": "ok", "added": added, "total_allowed": len(manifest["files"])}


@app.post("/deauthorize")
def deauthorize(req: DeauthorizeReq, api_key: str = Depends(get_api_key)):
    manifest = load_manifest()
    files = set(manifest.get("files", []))
    removed = []
    for f in req.files:
        if f in files:
            files.remove(f)
            removed.append(f)
    manifest["files"] = sorted(list(files))
    save_manifest(manifest)
    append_audit({"action": "deauthorize", "removed": removed, "by": api_key})
    return {"status": "ok", "removed": removed, "total_allowed": len(manifest["files"])}


@app.get("/get_kline")
def get_kline(name: str, start: Optional[str] = None, end: Optional[str] = None, max_bars: int = 500, api_key: str = Depends(get_api_key)):
    """读取指定白名单文件的 K 线数据。支持 CSV 和 Parquet。
    返回只包含常用列：ts, open, high, low, close, volume（如存在）。
    """
    if not is_allowed(name):
        raise HTTPException(status_code=403, detail="file not authorized")
    full = safe_join(name)
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="file not found")

    # 读取文件
    try:
        if name.lower().endswith('.csv'):
            df = pd.read_csv(full)
        else:
            # parquet support
            df = pd.read_parquet(full)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"read fail: {str(e)}")

    # 标准化时间列
    for c in ['ts', 'time', 'datetime']:
        if c in df.columns:
            df = df.rename(columns={c: 'ts'})
            break
    if 'ts' not in df.columns:
        raise HTTPException(status_code=400, detail="no timestamp column (ts/time/datetime) found")

    df['ts'] = pd.to_datetime(df['ts'], utc=True, errors='coerce')
    df = df.dropna(subset=['ts'])
    df = df.sort_values('ts')

    if start:
        try:
            df = df[df['ts'] >= pd.to_datetime(start)]
        except Exception:
            raise HTTPException(status_code=400, detail="invalid start datetime")
    if end:
        try:
            df = df[df['ts'] <= pd.to_datetime(end)]
        except Exception:
            raise HTTPException(status_code=400, detail="invalid end datetime")

    # 限制 max bars
    if max_bars <= 0:
        raise HTTPException(status_code=400, detail="max_bars must be > 0")
    if max_bars > MAX_BARS_LIMIT:
        max_bars = MAX_BARS_LIMIT

    out_df = df.tail(max_bars)
    rows_returned = len(out_df)
    meta = {"file_hash": file_fingerprint(full), "rows_returned": rows_returned, "truncated": rows_returned >= max_bars}
    append_audit({"action": "read_kline", "file": name, "rows_returned": rows_returned, "req_start": start, "req_end": end, "by": api_key})
    cols = [c for c in ['ts', 'open', 'high', 'low', 'close', 'volume'] if c in out_df.columns]
    return {"meta": meta, "ohlc": out_df[cols].to_dict(orient='records')}


@app.get("/read_tail")
def read_tail(name: str, n: int = 200, api_key: str = Depends(get_api_key)):
    """快捷接口：返回最新 n 条数据。"""
    return get_kline(name=name, max_bars=n, api_key=api_key)


@app.get("/audit")
def get_audit(limit: int = 200, api_key: str = Depends(get_api_key)):
    """返回最近的审计记录（JSON 行），默认最新 200 条。"""
    ensure_dirs()
    if not os.path.exists(AUDIT_LOG_PATH):
        return {"records": []}
    # 读取最后几行（文件可能很大，逐行倒读）
    records = []
    try:
        with open(AUDIT_LOG_PATH, 'r', encoding='utf-8') as f:
            # 读取所有行，取尾部（简单实现）
            lines = f.readlines()
            for ln in lines[-limit:]:
                try:
                    records.append(json.loads(ln))
                except Exception:
                    # 非 JSON 行忽略
                    continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"audit read fail: {str(e)}")
    return {"records": records}


# 占位：未来扩展点（向量检索/索引/窗口化）
# /vector_query 可在后续实现，建议把索引与检索留在本地，不上传到云


# -------------------- End of file --------------------
# 运行示例：
# 1) export MCP_API_KEY=your_secret
# 2) uvicorn mcp_fastapi:app --host 127.0.0.1 --port 8000
# API 示例请参考文件顶部注释

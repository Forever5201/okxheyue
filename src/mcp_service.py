"""
MCP (Model Control Protocol) 服务
基于 FastAPI 实现的本地数据访问服务

允许AI通过标准化API读取K线数据和技术指标
"""

import os
import json
import datetime
from pathlib import Path
from typing import List, Optional
import pandas as pd
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from pydantic import BaseModel
from src.logger import setup_logger

logger = setup_logger()

# 配置
DATA_ROOT = os.path.abspath("./kline_data")
MANIFEST_PATH = os.path.join(DATA_ROOT, "manifest.json")
AUDIT_LOG_PATH = os.path.join(DATA_ROOT, "audit.log")
ENV_API_KEY_NAME = "MCP_API_KEY"
MAX_RECORDS_LIMIT = 5000

# FastAPI 实例
app = FastAPI(
    title="AI Trading MCP Service",
    description="本地K线数据和技术指标访问服务",
    version="1.0.0"
)

# 数据模型
class AuthorizeReq(BaseModel):
    files: List[str]

class DeauthorizeReq(BaseModel):
    files: List[str]

class DataQueryReq(BaseModel):
    timeframe: str
    symbol: Optional[str] = "BTC-USD-SWAP"
    data_type: str = "combined"  # kline, indicators, combined
    max_records: Optional[int] = 500

# 工具函数
def ensure_dirs():
    """确保目录存在"""
    os.makedirs(DATA_ROOT, exist_ok=True)
    if not os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump({"files": []}, f, ensure_ascii=False, indent=2)

def load_manifest():
    """加载文件清单"""
    ensure_dirs()
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_manifest(manifest: dict):
    """原子性保存文件清单"""
    ensure_dirs()
    tmp = MANIFEST_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MANIFEST_PATH)

def append_audit(entry: dict):
    """追加审计日志"""
    ensure_dirs()
    entry = dict(entry)
    entry["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def is_file_allowed(filename: str) -> bool:
    """检查文件是否在白名单中"""
    manifest = load_manifest()
    return filename in manifest.get("files", [])

def safe_join(relative_path: str) -> str:
    """安全的路径拼接，防止路径穿越"""
    if not relative_path or ".." in relative_path or relative_path.startswith("/"):
        raise HTTPException(status_code=400, detail="invalid file path")
    
    full_path = os.path.join(DATA_ROOT, relative_path)
    full_path = os.path.abspath(full_path)
    
    # 确保路径在DATA_ROOT下
    if not full_path.startswith(os.path.abspath(DATA_ROOT) + os.sep) and full_path != os.path.abspath(DATA_ROOT):
        raise HTTPException(status_code=400, detail="invalid file path")
    
    return full_path

def file_fingerprint(path: str) -> str:
    """生成文件指纹"""
    try:
        st = os.stat(path)
        return f"{st.st_mtime_ns}-{st.st_size}"
    except:
        return "unknown"

# 鉴权依赖
def get_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """API Key验证"""
    expected_key = os.environ.get(ENV_API_KEY_NAME)
    if not expected_key:
        raise HTTPException(
            status_code=500, 
            detail=f"Server misconfigured: {ENV_API_KEY_NAME} environment variable not set"
        )
    
    if x_api_key is None:
        raise HTTPException(
            status_code=401, 
            detail="Missing API key header 'x-api-key'"
        )
    
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return x_api_key

# API 端点
@app.on_event("startup")
def startup_event():
    """启动事件"""
    ensure_dirs()
    logger.info("MCP Service started")

@app.get("/")
def root():
    """根路径"""
    return {
        "service": "AI Trading MCP Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "/list_files",
            "/authorize",
            "/deauthorize", 
            "/query_data",
            "/get_latest_data"
        ]
    }

@app.get("/list_files")
def list_files(api_key: str = Depends(get_api_key)):
    """列出可访问的文件"""
    try:
        manifest = load_manifest()
        files = []
        
        for filename in manifest.get("files", []):
            try:
                full_path = safe_join(filename)
                if os.path.exists(full_path):
                    stat_info = os.stat(full_path)
                    files.append({
                        "filename": filename,
                        "size": stat_info.st_size,
                        "modified": datetime.datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                        "fingerprint": file_fingerprint(full_path)
                    })
            except:
                continue
        
        return {"files": files, "total": len(files)}
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")

@app.post("/authorize")
def authorize_files(req: AuthorizeReq, api_key: str = Depends(get_api_key)):
    """授权访问文件"""
    try:
        manifest = load_manifest()
        current_files = set(manifest.get("files", []))
        
        # 验证文件存在
        valid_files = []
        for filename in req.files:
            try:
                full_path = safe_join(filename)
                if os.path.exists(full_path):
                    valid_files.append(filename)
            except:
                continue
        
        # 更新清单
        current_files.update(valid_files)
        manifest["files"] = list(current_files)
        save_manifest(manifest)
        
        # 审计日志
        append_audit({
            "action": "authorize",
            "files": valid_files,
            "api_key_hash": hash(api_key) % 10000
        })
        
        return {"authorized": valid_files, "total": len(current_files)}
        
    except Exception as e:
        logger.error(f"Error authorizing files: {e}")
        raise HTTPException(status_code=500, detail="Authorization failed")

@app.post("/deauthorize")
def deauthorize_files(req: DeauthorizeReq, api_key: str = Depends(get_api_key)):
    """取消授权文件"""
    try:
        manifest = load_manifest()
        current_files = set(manifest.get("files", []))
        
        # 移除指定文件
        for filename in req.files:
            current_files.discard(filename)
        
        manifest["files"] = list(current_files)
        save_manifest(manifest)
        
        # 审计日志
        append_audit({
            "action": "deauthorize",
            "files": req.files,
            "api_key_hash": hash(api_key) % 10000
        })
        
        return {"deauthorized": req.files, "remaining": len(current_files)}
        
    except Exception as e:
        logger.error(f"Error deauthorizing files: {e}")
        raise HTTPException(status_code=500, detail="Deauthorization failed")

@app.post("/query_data")
def query_data(req: DataQueryReq, api_key: str = Depends(get_api_key)):
    """查询交易数据"""
    try:
        # 查找匹配的文件
        manifest = load_manifest()
        available_files = manifest.get("files", [])
        
        # 根据时间周期和数据类型过滤文件
        matching_files = [
            f for f in available_files
            if req.timeframe in f and req.data_type in f and req.symbol in f
        ]
        
        if not matching_files:
            return {"data": [], "message": f"No data found for {req.symbol} {req.timeframe} {req.data_type}"}
        
        # 取最新的文件
        latest_file = max(matching_files, key=lambda f: os.path.getmtime(safe_join(f)))
        
        # 读取数据
        full_path = safe_join(latest_file)
        df = pd.read_csv(full_path)
        
        # 限制记录数
        max_records = min(req.max_records or 500, MAX_RECORDS_LIMIT)
        df = df.tail(max_records)
        
        # 审计日志
        append_audit({
            "action": "query_data",
            "file": latest_file,
            "records": len(df),
            "api_key_hash": hash(api_key) % 10000
        })
        
        return {
            "data": df.to_dict('records'),
            "file": latest_file,
            "records": len(df),
            "columns": list(df.columns)
        }
        
    except Exception as e:
        logger.error(f"Error querying data: {e}")
        raise HTTPException(status_code=500, detail="Data query failed")

@app.get("/get_latest_data")
def get_latest_data(
    timeframe: str = Query(..., description="时间周期，如1H, 4H, 1D"),
    symbol: str = Query("BTC-USD-SWAP", description="交易对"),
    data_type: str = Query("combined", description="数据类型"),
    max_records: int = Query(100, description="最大记录数"),
    api_key: str = Depends(get_api_key)
):
    """获取最新数据的GET接口"""
    req = DataQueryReq(
        timeframe=timeframe,
        symbol=symbol,
        data_type=data_type,
        max_records=max_records
    )
    return query_data(req, api_key)
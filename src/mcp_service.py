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
        f.write(json.dumps(entry, ensure_ascii=False) + "\\n")

def is_file_allowed(filename: str) -> bool:
    """检查文件是否在白名单中"""
    manifest = load_manifest()
    return filename in manifest.get("files", [])\n\ndef safe_join(relative_path: str) -> str:\n    \"\"\"安全的路径拼接，防止路径穿越\"\"\"\n    if not relative_path or \"..\" in relative_path or relative_path.startswith(\"/\"):\n        raise HTTPException(status_code=400, detail=\"invalid file path\")\n    \n    full_path = os.path.join(DATA_ROOT, relative_path)\n    full_path = os.path.abspath(full_path)\n    \n    # 确保路径在DATA_ROOT下\n    if not full_path.startswith(os.path.abspath(DATA_ROOT) + os.sep) and full_path != os.path.abspath(DATA_ROOT):\n        raise HTTPException(status_code=400, detail=\"invalid file path\")\n    \n    return full_path\n\ndef file_fingerprint(path: str) -> str:\n    \"\"\"生成文件指纹\"\"\"\n    try:\n        st = os.stat(path)\n        return f\"{st.st_mtime_ns}-{st.st_size}\"\n    except:\n        return \"unknown\"\n\n# 鉴权依赖\ndef get_api_key(x_api_key: Optional[str] = Header(None)) -> str:\n    \"\"\"API Key验证\"\"\"\n    expected_key = os.environ.get(ENV_API_KEY_NAME)\n    if not expected_key:\n        raise HTTPException(\n            status_code=500, \n            detail=f\"Server misconfigured: {ENV_API_KEY_NAME} environment variable not set\"\n        )\n    \n    if x_api_key is None:\n        raise HTTPException(\n            status_code=401, \n            detail=\"Missing API key header 'x-api-key'\"\n        )\n    \n    if x_api_key != expected_key:\n        raise HTTPException(status_code=401, detail=\"Invalid API key\")\n    \n    return x_api_key\n\n# API 端点\n@app.on_event(\"startup\")\ndef startup_event():\n    \"\"\"启动事件\"\"\"\n    ensure_dirs()\n    logger.info(\"MCP Service started\")\n\n@app.get(\"/\")\ndef root():\n    \"\"\"根路径\"\"\"\n    return {\n        \"service\": \"AI Trading MCP Service\",\n        \"version\": \"1.0.0\",\n        \"status\": \"running\",\n        \"endpoints\": [\n            \"/list_files\",\n            \"/authorize\",\n            \"/deauthorize\", \n            \"/query_data\",\n            \"/get_latest_data\",\n            \"/list_timeframes\",\n            \"/audit_log\"\n        ]\n    }\n\n@app.get(\"/list_files\")\ndef list_allowed_files(api_key: str = Depends(get_api_key)):\n    \"\"\"列出所有被授权的文件\"\"\"\n    manifest = load_manifest()\n    append_audit({\"action\": \"list_files\", \"user\": api_key[:8] + \"...\"})  # 只记录部分key\n    return manifest\n\n@app.post(\"/authorize\")\ndef authorize_files(req: AuthorizeReq, api_key: str = Depends(get_api_key)):\n    \"\"\"授权文件访问\"\"\"\n    manifest = load_manifest()\n    files_set = set(manifest.get(\"files\", []))\n    added = []\n    \n    for file_path in req.files:\n        # 检查路径安全性\n        try:\n            full_path = safe_join(file_path)\n        except HTTPException as e:\n            raise HTTPException(status_code=400, detail=f\"Invalid file path {file_path}: {e.detail}\")\n        \n        if not os.path.exists(full_path):\n            raise HTTPException(status_code=404, detail=f\"File not found: {file_path}\")\n        \n        if file_path not in files_set:\n            files_set.add(file_path)\n            added.append(file_path)\n    \n    manifest[\"files\"] = sorted(list(files_set))\n    save_manifest(manifest)\n    \n    append_audit({\n        \"action\": \"authorize\", \n        \"added\": added, \n        \"user\": api_key[:8] + \"...\"\n    })\n    \n    return {\n        \"status\": \"success\",\n        \"added\": added,\n        \"total_authorized\": len(manifest[\"files\"])\n    }\n\n@app.post(\"/deauthorize\")\ndef deauthorize_files(req: DeauthorizeReq, api_key: str = Depends(get_api_key)):\n    \"\"\"取消文件授权\"\"\"\n    manifest = load_manifest()\n    files_set = set(manifest.get(\"files\", []))\n    removed = []\n    \n    for file_path in req.files:\n        if file_path in files_set:\n            files_set.remove(file_path)\n            removed.append(file_path)\n    \n    manifest[\"files\"] = sorted(list(files_set))\n    save_manifest(manifest)\n    \n    append_audit({\n        \"action\": \"deauthorize\", \n        \"removed\": removed, \n        \"user\": api_key[:8] + \"...\"\n    })\n    \n    return {\n        \"status\": \"success\",\n        \"removed\": removed,\n        \"total_authorized\": len(manifest[\"files\"])\n    }\n\n@app.get(\"/list_timeframes\")\ndef list_available_timeframes(api_key: str = Depends(get_api_key)):\n    \"\"\"列出可用的时间周期\"\"\"\n    try:\n        timeframes = []\n        data_path = Path(DATA_ROOT)\n        \n        if data_path.exists():\n            for item in data_path.iterdir():\n                if item.is_dir() and not item.name.startswith('.'):\n                    timeframes.append(item.name)\n        \n        append_audit({\"action\": \"list_timeframes\", \"user\": api_key[:8] + \"...\"})\n        \n        return {\n            \"timeframes\": sorted(timeframes),\n            \"total\": len(timeframes)\n        }\n    except Exception as e:\n        logger.error(f\"Error listing timeframes: {e}\")\n        raise HTTPException(status_code=500, detail=str(e))\n\n@app.post(\"/query_data\")\ndef query_kline_data(req: DataQueryReq, api_key: str = Depends(get_api_key)):\n    \"\"\"查询K线数据\"\"\"\n    try:\n        # 构建文件路径\n        timeframe = req.timeframe\n        symbol = req.symbol\n        data_type = req.data_type\n        max_records = min(req.max_records or 500, MAX_RECORDS_LIMIT)\n        \n        # 查找最新的数据文件\n        data_dir = Path(DATA_ROOT) / timeframe / data_type\n        \n        if not data_dir.exists():\n            raise HTTPException(status_code=404, detail=f\"No data found for timeframe: {timeframe}\")\n        \n        # 查找匹配的最新文件\n        pattern = f\"{symbol}_{timeframe}_{data_type}_*.parquet\"\n        parquet_files = list(data_dir.glob(f\"{symbol}_{timeframe}_{data_type}_*.parquet\"))\n        \n        if not parquet_files:\n            # 尝试CSV文件\n            csv_files = list(data_dir.glob(f\"{symbol}_{timeframe}_{data_type}_*.csv\"))\n            if not csv_files:\n                raise HTTPException(\n                    status_code=404, \n                    detail=f\"No data files found for {symbol} {timeframe} {data_type}\"\n                )\n            latest_file = max(csv_files, key=lambda x: x.stat().st_mtime)\n            df = pd.read_csv(latest_file)\n        else:\n            latest_file = max(parquet_files, key=lambda x: x.stat().st_mtime)\n            df = pd.read_parquet(latest_file)\n        \n        # 检查文件是否被授权\n        relative_path = str(latest_file.relative_to(Path(DATA_ROOT)))\n        if not is_file_allowed(relative_path):\n            raise HTTPException(\n                status_code=403, \n                detail=f\"File not authorized: {relative_path}\"\n            )\n        \n        # 限制返回记录数\n        if len(df) > max_records:\n            df = df.tail(max_records)\n        \n        # 记录审计\n        append_audit({\n            \"action\": \"query_data\",\n            \"timeframe\": timeframe,\n            \"symbol\": symbol,\n            \"data_type\": data_type,\n            \"file\": relative_path,\n            \"records_returned\": len(df),\n            \"user\": api_key[:8] + \"...\"\n        })\n        \n        return {\n            \"status\": \"success\",\n            \"metadata\": {\n                \"timeframe\": timeframe,\n                \"symbol\": symbol,\n                \"data_type\": data_type,\n                \"file_path\": relative_path,\n                \"records_count\": len(df),\n                \"columns\": list(df.columns),\n                \"file_fingerprint\": file_fingerprint(str(latest_file))\n            },\n            \"data\": df.to_dict(orient=\"records\")\n        }\n        \n    except Exception as e:\n        logger.error(f\"Error querying data: {e}\")\n        if isinstance(e, HTTPException):\n            raise e\n        raise HTTPException(status_code=500, detail=str(e))\n\n@app.get(\"/get_latest_data\")\ndef get_latest_data(\n    timeframe: str = Query(..., description=\"时间周期\"),\n    symbol: str = Query(\"BTC-USD-SWAP\", description=\"交易对\"),\n    data_type: str = Query(\"combined\", description=\"数据类型\"),\n    max_records: int = Query(100, description=\"最大记录数\"),\n    api_key: str = Depends(get_api_key)\n):\n    \"\"\"获取最新数据的便捷接口\"\"\"\n    req = DataQueryReq(\n        timeframe=timeframe,\n        symbol=symbol, \n        data_type=data_type,\n        max_records=max_records\n    )\n    return query_kline_data(req, api_key)\n\n@app.get(\"/audit_log\")\ndef get_audit_log(\n    limit: int = Query(100, description=\"返回记录数限制\"),\n    api_key: str = Depends(get_api_key)\n):\n    \"\"\"获取审计日志\"\"\"\n    ensure_dirs()\n    \n    if not os.path.exists(AUDIT_LOG_PATH):\n        return {\"records\": []}\n    \n    try:\n        records = []\n        with open(AUDIT_LOG_PATH, 'r', encoding='utf-8') as f:\n            lines = f.readlines()\n            for line in lines[-limit:]:\n                try:\n                    records.append(json.loads(line.strip()))\n                except json.JSONDecodeError:\n                    continue\n        \n        append_audit({\"action\": \"get_audit_log\", \"limit\": limit, \"user\": api_key[:8] + \"...\"})\n        \n        return {\"records\": records, \"total\": len(records)}\n        \n    except Exception as e:\n        logger.error(f\"Error reading audit log: {e}\")\n        raise HTTPException(status_code=500, detail=str(e))\n\n@app.get(\"/health\")\ndef health_check():\n    \"\"\"健康检查\"\"\"\n    return {\n        \"status\": \"healthy\",\n        \"timestamp\": datetime.datetime.utcnow().isoformat() + \"Z\",\n        \"data_root\": DATA_ROOT,\n        \"data_root_exists\": os.path.exists(DATA_ROOT)\n    }\n\nif __name__ == \"__main__\":\n    import uvicorn\n    uvicorn.run(app, host=\"0.0.0.0\", port=8000, log_level=\"info\")"
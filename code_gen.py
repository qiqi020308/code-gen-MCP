#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
# 新增编码强制
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
import json
import os
import requests
from typing import Any, Dict, List, Optional

# ---------- 配置 ----------
# 后端 code-gen 服务地址（docker run 时可用 -e CODE_GEN_API=http://<ip>:<port> 覆盖）
BASE_URL = os.environ.get("CODE_GEN_API", "http://localhost:6969")
# HTTP 模式监听端口/主机（docker run 时可用 -e MCP_PORT=xxxx -e MCP_HOST=0.0.0.0 覆盖）
MCP_PORT = int(os.environ.get("MCP_PORT", "6968"))
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")

# HTTP 超时：常规接口 15 秒；代码生成较慢（多表 × 多模板渲染），单独放宽到 120 秒
DEFAULT_TIMEOUT = int(os.environ.get("CODE_GEN_TIMEOUT", "15"))
GENERATE_TIMEOUT = int(os.environ.get("CODE_GEN_GENERATE_TIMEOUT", "120"))

# ---------- API 调用辅助 ----------
def call_api(method: str, path: str, data: Optional[Any] = None,
             params: Optional[Dict] = None, is_raw: bool = False,
             timeout: int = DEFAULT_TIMEOUT) -> Any:
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    try:
        if method.upper() == "GET":
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        else:
            resp = requests.post(url, json=data, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()
        if is_raw:
            return result
        if result.get("code") == "0":
            return result.get("data")
        else:
            raise ValueError(f"业务错误: {result.get('msg', '未知')}")
    except Exception as e:
        raise ValueError(f"API调用失败: {str(e)}")

# ---------- 工具函数（与之前一致） ----------
def datasource_add(config: Dict) -> None:
    call_api("POST", "/datasource/add", data=config)

def datasource_list() -> List[Dict]:
    return call_api("POST", "/datasource/list", data={})

def datasource_update(config: Dict) -> None:
    call_api("POST", "/datasource/update", data=config)

def datasource_delete(id: int) -> None:
    call_api("POST", "/datasource/del", data={"id": id})

def datasource_tables(id: int) -> List[Dict]:
    return call_api("POST", f"/datasource/table/{id}", data={})

def datasource_test(config: Dict) -> None:
    call_api("POST", "/datasource/test", data=config)

def datasource_dbtypes() -> List[Dict]:
    return call_api("POST", "/datasource/dbtype", data={})

def template_add(template: Dict) -> Dict:
    return call_api("POST", "/template/add", data=template)

def template_get(id: int) -> Optional[Dict]:
    return call_api("POST", f"/template/get/{id}", data={})

def template_list(groupId: Optional[int] = None) -> List[Dict]:
    params = {"groupId": groupId} if groupId is not None else {}
    return call_api("POST", "/template/list", params=params, data={})

def template_update(template: Dict) -> None:
    call_api("POST", "/template/update", data=template)

def template_delete(id: int) -> None:
    call_api("POST", "/template/del", data={"id": id})

def template_save(groupId: int, name: str, content: str,
                  groupName: Optional[str] = None,
                  folder: Optional[str] = None,
                  fileName: Optional[str] = None) -> None:
    payload = {"groupId": groupId, "name": name, "content": content}
    if groupName: payload["groupName"] = groupName
    if folder: payload["folder"] = folder
    if fileName: payload["fileName"] = fileName
    call_api("POST", "/template/save", data=payload)

def template_copy(id: int, name: str) -> None:
    call_api("POST", "/template/copy", data={"id": id, "name": name})

def group_list() -> List[Dict]:
    return call_api("POST", "/group/list", data={})

def group_get(id: int) -> Optional[Dict]:
    return call_api("POST", f"/group/get/{id}", data={})

def group_add(groupName: str) -> Dict:
    return call_api("POST", "/group/add", data={"groupName": groupName})

def group_update(id: int, groupName: str) -> None:
    call_api("POST", "/group/update", data={"id": id, "groupName": groupName})

def group_delete(id: int) -> None:
    call_api("POST", "/group/del", data={"id": id})

def type_list() -> List[Dict]:
    return call_api("POST", "/type/list", data={})

def type_get_by_id(id: int) -> Dict:
    return call_api("POST", "/type/getById", params={"id": id}, data={}, is_raw=True)

def type_update(mappings: List[Dict]) -> None:
    # 该接口的请求体是数组而非对象；统一走 call_api 以获得超时与错误处理能力
    # （原实现直接 requests.post 且未设 timeout，后端不可达时会永久挂起）
    call_api("POST", "/type/update", data=mappings)

def generate_code(datasourceConfigId: int, tableNames: List[str],
                  templateConfigIdList: List[int],
                  packageName: Optional[str] = None,
                  delPrefix: Optional[str] = None,
                  author: Optional[str] = None,
                  charset: str = "UTF-8") -> List[Dict]:
    payload = {
        "datasourceConfigId": datasourceConfigId,
        "tableNames": tableNames,
        "templateConfigIdList": templateConfigIdList,
        "packageName": packageName,
        "delPrefix": delPrefix,
        "author": author,
        "charset": charset
    }
    # 代码生成涉及表结构查询 + 多模板渲染，耗时明显高于普通接口，使用更长超时
    return call_api("POST", "/generate/code", data=payload, timeout=GENERATE_TIMEOUT)

def history_list() -> List[Dict]:
    return call_api("POST", "/history/list", data={})

def history_delete(id: int) -> int:
    return call_api("POST", f"/history/delete/{id}", data={})

# ---------- 工具注册表 ----------
TOOLS = {
    "datasource_add": {
        "fn": lambda args: datasource_add(args["config"]),
        "desc": "新增一个数据库数据源配置，支持 MySQL/Oracle/SQL Server/PostgreSQL/达梦/OpenGAUSS。"
                "建议在新增前先调用 datasource_test 验证连接参数可用。"
                "注意：本接口不会返回新数据源的 id，新增后请用 datasource_list 查询获取 id。",
        "schema": {"type": "object", "properties": {"config": {"type": "object"}}, "required": ["config"]}
    },
    "datasource_list": {
        "fn": lambda args: datasource_list(),
        "desc": "列出所有已保存且未删除的数据源配置，返回 id、数据库类型、主机、端口等信息。"
                "生成代码前通常先用本工具拿到数据源 id。"
                "注意：返回结果包含数据库明文密码，请勿在日志或对话中泄露。",
        "schema": {"type": "object", "properties": {}}
    },
    "datasource_update": {
        "fn": lambda args: datasource_update(args["config"]),
        "desc": "修改数据源配置。重要：这是【全字段覆盖】更新，不是局部更新，"
                "未提交的字段会被清空。必须先调用 datasource_list 拿到完整对象，在其基础上修改后再整体提交。",
        "schema": {"type": "object", "properties": {"config": {"type": "object"}}, "required": ["config"]}
    },
    "datasource_delete": {
        "fn": lambda args: datasource_delete(args["id"]),
        "desc": "删除数据源（软删除，记录仍保留在库中，只是不再出现在列表里）。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    },
    "datasource_tables": {
        "fn": lambda args: datasource_tables(args["id"]),
        "desc": "查询指定数据源中的所有数据表，返回表名和表注释。"
                "生成代码前用它确认目标表的准确名称（SQL Server 表名可能带 schema 前缀）。"
                "注意：只返回表信息，不包含字段定义。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    },
    "datasource_test": {
        "fn": lambda args: datasource_test(args["config"]),
        "desc": "测试一组数据库连接参数是否可用，成功返回空，失败会给出具体 JDBC 错误。"
                "强烈建议在 datasource_add / datasource_update 之前先调用本工具验证。",
        "schema": {"type": "object", "properties": {"config": {"type": "object"}}, "required": ["config"]}
    },
    "datasource_dbtypes": {
        "fn": lambda args: datasource_dbtypes(),
        "desc": "查询当前服务支持的数据库类型列表，返回展示名称 label 与类型编号 dbType 的对应关系"
                "（如 MySQL=1、Oracle=2）。构造数据源配置时需要用到这里的 dbType。",
        "schema": {"type": "object", "properties": {}}
    },
    "template_add": {
        "fn": lambda args: template_add(args["template"]),
        "desc": "在指定分组下新增一个 Velocity 代码模板，需要提供 groupId、name、fileName、folder 和 content。"
                "content 首行可用元信息指定输出文件名与目录，格式：## filename=xxx.java, folder=entity"
                "返回新增后的模板对象（含 id）。同分组内 name 不可重复。",
        "schema": {"type": "object", "properties": {"template": {"type": "object"}}, "required": ["template"]}
    },
    "template_get": {
        "fn": lambda args: template_get(args["id"]),
        "desc": "按 id 查询单个模板的完整详情，返回数据库中保存的原始 content。"
                "注意：与 template_list 不同，本接口不会重建 content 首行的元信息。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    },
    "template_list": {
        "fn": lambda args: template_list(args.get("groupId")),
        "desc": "查询模板列表，传 groupId 时只返回该分组的模板，不传则返回全部未删除模板。"
                "返回各模板的 id 和名称，generate_code 需要用到这里的 id。",
        "schema": {"type": "object", "properties": {"groupId": {"type": "integer"}}}
    },
    "template_update": {
        "fn": lambda args: template_update(args["template"]),
        "desc": "修改模板内容或属性。省略或传 null 的字段保持原值不变，如需清空某字段请传空字符串。"
                "建议同时提交 groupId 和 name，服务端据此做同组重名检查。",
        "schema": {"type": "object", "properties": {"template": {"type": "object"}}, "required": ["template"]}
    },
    "template_delete": {
        "fn": lambda args: template_delete(args["id"]),
        "desc": "删除模板（软删除）。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    },
    "template_save": {
        "fn": lambda args: template_save(
            args["groupId"], args["name"], args["content"],
            args.get("groupName"), args.get("folder"), args.get("fileName")
        ),
        "desc": "按 (name, groupId) 新增或更新模板（upsert，存在则更新、不存在则新增），适合批量导入模板。"
                "fileName 或 folder 留空时，会自动从 content 首行的 ## filename=..., folder=... 元信息推断。"
                "本接口不返回模板对象，需要 id 请再调用 template_list。",
        "schema": {
            "type": "object",
            "properties": {
                "groupId": {"type": "integer"},
                "name": {"type": "string"},
                "content": {"type": "string"},
                "groupName": {"type": "string"},
                "folder": {"type": "string"},
                "fileName": {"type": "string"}
            },
            "required": ["groupId", "name", "content"]
        }
    },
    "template_copy": {
        "fn": lambda args: template_copy(args["id"], args["name"]),
        "desc": "复制一个现有模板并指定新名称，副本保留源模板的分组、输出目录和模板内容。"
                "注意：始终复制到源模板所在的分组；若该分组下已有同名模板，会直接覆盖其内容。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}, "required": ["id", "name"]}
    },
    "group_list": {
        "fn": lambda args: group_list(),
        "desc": "列出所有模板分组，返回分组 id 与名称。分组用于把不同框架或不同规范的模板归类管理，"
                "例如 default、mybatis-plus 各自一套。",
        "schema": {"type": "object", "properties": {}}
    },
    "group_get": {
        "fn": lambda args: group_get(args["id"]),
        "desc": "按 id 查询单个模板分组的详情（只包含未删除的分组）。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    },
    "group_add": {
        "fn": lambda args: group_add(args["groupName"]),
        "desc": "新增一个模板分组，便于按项目或框架（如 mybatis-plus）隔离不同套代码模板。"
                "分组名称不可与现有分组重复，返回新增后的分组对象（含 id）。",
        "schema": {"type": "object", "properties": {"groupName": {"type": "string"}}, "required": ["groupName"]}
    },
    "group_update": {
        "fn": lambda args: group_update(args["id"], args["groupName"]),
        "desc": "重命名模板分组。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}, "groupName": {"type": "string"}}, "required": ["id", "groupName"]}
    },
    "group_delete": {
        "fn": lambda args: group_delete(args["id"]),
        "desc": "删除模板分组（软删除），同时会软删除该分组下的所有模板。"
                "注意：系统要求至少保留一个分组，删除最后一个分组会被拒绝。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    },
    "type_list": {
        "fn": lambda args: type_list(),
        "desc": "列出数据库字段类型到 Java 类型的映射规则，包含 dbType（如 varchar）、"
                "baseType（如 String）和 boxType（如 String）的对应关系。",
        "schema": {"type": "object", "properties": {}}
    },
    "type_get_by_id": {
        "fn": lambda args: type_get_by_id(args["id"]),
        "desc": "按 id 查询单条类型映射规则，返回该映射对象本身（无统一响应外层）。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    },
    "type_update": {
        "fn": lambda args: type_update(args["mappings"]),
        "desc": "批量修改类型映射规则，入参是映射对象数组（不是 {list:[...]} 包装）。"
                "用于自定义数据库字段类型与 Java 类型的对应关系，例如把 datetime 映射为 LocalDateTime。",
        "schema": {"type": "object", "properties": {"mappings": {"type": "array", "items": {"type": "object"}}}, "required": ["mappings"]}
    },
    "generate_code": {
        "fn": lambda args: generate_code(
            args["datasourceConfigId"], args["tableNames"], args["templateConfigIdList"],
            args.get("packageName"), args.get("delPrefix"), args.get("author"), args.get("charset", "UTF-8")
        ),
        "desc": "【核心工具】根据数据库表结构和 Velocity 模板生成代码。"
                "传入数据源 id、表名列表、模板 id 列表，返回每个生成文件的目录、文件名和完整代码内容。"
                "典型流程：先用 datasource_tables 拿到表名，再用 template_list 拿到模板 id，最后调用本工具。"
                "delPrefix 用于生成类名时去掉表名前缀（多个前缀用逗号分隔），packageName 指定包名，"
                "author 会填入模板中的作者变量。生成记录会异步写入历史，可用 history_list 查看。",
        "schema": {
            "type": "object",
            "properties": {
                "datasourceConfigId": {"type": "integer"},
                "tableNames": {"type": "array", "items": {"type": "string"}},
                "templateConfigIdList": {"type": "array", "items": {"type": "integer"}},
                "packageName": {"type": "string"},
                "delPrefix": {"type": "string"},
                "author": {"type": "string"},
                "charset": {"type": "string"}
            },
            "required": ["datasourceConfigId", "tableNames", "templateConfigIdList"]
        }
    },
    "history_list": {
        "fn": lambda args: history_list(),
        "desc": "查询代码生成的历史记录，按 id 倒序返回，包含当次生成的参数、生成时间、"
                "数据源摘要和所用模板名称。可用于追溯某次生成用了哪些表和模板。",
        "schema": {"type": "object", "properties": {}}
    },
    "history_delete": {
        "fn": lambda args: history_delete(args["id"]),
        "desc": "按 id 删除一条生成历史记录（物理删除，不可恢复），返回实际删除的行数。",
        "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    }
}

def is_notification(request: Dict) -> bool:
    """判断是否为通知类请求。

    MCP/JSON-RPC 规范：通知（notification）不得返回任何响应。
    兼容三种写法：无 id、notifications/* 前缀、裸 initialized。
    """
    method = str(request.get("method", ""))
    if request.get("id") is None:
        return True
    return method == "initialized" or method.startswith("notifications/")


# ---------- JSON-RPC 请求处理（同步） ----------
def handle_request(request: Dict) -> Optional[Dict]:
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    # 通知类请求：返回 None 表示"不响应"，调用方必须据此跳过输出
    if is_notification(request):
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-11-25",
                "serverInfo": {
                    "name": "code-gen-mcp-server",
                    "version": "1.0.0"
                },
                "capabilities": {"tools": {}}
            }
        }
    elif method == "tools/list":
        # description 直接决定 AI 能否正确选择工具，必须提供语义化说明而非把下划线换成空格
        tools_list = [
            {
                "name": name,
                "description": info.get("desc") or name.replace("_", " "),
                "inputSchema": info["schema"],
            }
            for name, info in TOOLS.items()
        ]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools_list}
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
            }
        try:
            result = TOOLS[tool_name]["fn"](args)
            text = json.dumps(result, ensure_ascii=False, indent=2) if result is not None else "null"
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)}
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not supported"}
        }
        
# ---------- 主循环（同步，stdio 模式） ----------
def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle_request(req)
        if resp is None:
            continue  # 通知类请求：按规范不输出任何响应，避免写入 "null" 破坏协议流
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


# ---------- HTTP 模式（MCP Streamable HTTP transport） ----------
# 服务器上以 HTTP 模式运行后，远端 Claude Code 可通过
#   claude mcp add code-gen --transport http http://<host>:<port>/mcp
# 远程调用本 MCP 服务器。默认无鉴权，建议设置 CODE_GEN_TOKEN 并配合防火墙限制。
def main_http(host: str = "0.0.0.0", port: int = 6968) -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    TOKEN = os.environ.get("CODE_GEN_TOKEN", "")

    class MCPHandler(BaseHTTPRequestHandler):
        def _send_json(self, code: int, obj: Any) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def _send_cors_headers(self) -> None:
            # 允许浏览器端 / 跨域的 MCP 客户端直连（配合 CODE_GEN_TOKEN 使用）
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS, DELETE")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, Authorization, Mcp-Session-Id")
            self.send_header("Access-Control-Expose-Headers", "Mcp-Session-Id")

        def _check_token(self) -> bool:
            if not TOKEN:
                return True
            auth = self.headers.get("Authorization", "")
            return auth == f"Bearer {TOKEN}"

        def do_POST(self):
            # 路径不限（/mcp 或任意路径均可），与 URL 匹配无关
            if not self._check_token():
                self._send_json(401, {"jsonrpc": "2.0", "id": None,
                                      "error": {"code": -32000, "message": "unauthorized"}})
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length)
            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                self._send_json(400, {"jsonrpc": "2.0", "id": None,
                                      "error": {"code": -32700, "message": "parse error"}})
                return
            method = req.get("method", "")
            # 通知类请求（无 id / notifications/* / initialized）返回 202 无响应体
            if is_notification(req):
                self.send_response(202)
                self._send_cors_headers()
                self.end_headers()
                return
            resp = handle_request(req)
            self._send_json(200, resp)

        def do_OPTIONS(self):
            # CORS 预检
            self.send_response(204)
            self._send_cors_headers()
            self.end_headers()

        def do_GET(self):
            # 本实现为纯 POST（JSON 响应）；GET 探测返回 405 表示不支持 SSE 流
            self.send_response(405)
            self.end_headers()

        def log_message(self, *args):
            pass  # 静默访问日志

    server = ThreadingHTTPServer((host, port), MCPHandler)
    print(f"[code-gen-mcp] HTTP server listening on http://{host}:{port}/mcp (stdio 模式未启用)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    if "--http" in sys.argv:
        # 默认取环境变量（MCP_HOST / MCP_PORT），命令行 --host / --port 优先
        _port = MCP_PORT
        if "--port" in sys.argv:
            _idx = sys.argv.index("--port")
            if _idx + 1 < len(sys.argv):
                _port = int(sys.argv[_idx + 1])
        _host = MCP_HOST
        if "--host" in sys.argv:
            _idx = sys.argv.index("--host")
            if _idx + 1 < len(sys.argv):
                _host = sys.argv[_idx + 1]
        main_http(host=_host, port=_port)
    else:
        main()
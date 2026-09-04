# code-gen-mcp（代码生成器 MCP 服务器）

> 把代码生成器 [code-gen](https://gitee.com/durcframework/code-gen) 包装成 **MCP 服务器**，
> 让 AI（Claude Code / Cursor / Cline 等）按**团队统一模板**生成代码，从源头保证风格一致。

---

## 这个项目解决什么问题

团队代码风格不统一，通常有三个层次的应对方式：

| 层次 | 做法 | 问题 |
| --- | --- | --- |
| 规范文档 | 写《Java 开发规范》让大家遵守 | 靠人自觉，新人记不全 |
| 事后检查 | Checkstyle / Alibaba P3C | 只能拦"写错"，挡不住"写法不一样" |
| **源头统一** | **模板 + 强制单点出口** | **本项目的做法** |

本项目的思路是：**不让 AI 自由发挥去"写"代码，而是让它去"调用"代码生成器。**

AI 只能走 MCP 这一条路，MCP 的出口是 Velocity 模板，而模板就是团队的规范。
这样无论谁、无论哪个模型来生成，产出的代码都像出自同一个人之手。

---

## 架构

```
AI 客户端（Claude Code / Cursor / Cline 等）
        │
        │  MCP 协议（标准输入输出 或 HTTP）
        ▼
┌─────────────────────────────┐
│  code_gen.py   ← 本项目      │
│  25 个 MCP 工具，无状态转发   │
└─────────────────────────────┘
        │
        │  HTTP REST（/datasource /template /group /type /generate /history）
        ▼
┌─────────────────────────────┐
│  code-gen 后端服务（:6969）  │
│  Solon + Mybatis，内置 Web UI│
└─────────────────────────────┘
        │  JDBC（只读表结构）
        ▼
   业务数据库（MySQL / Oracle / SQL Server / PostgreSQL / 达梦 / OpenGAUSS）
```

本项目**不重复实现**代码生成能力，只做三件事：

1. 把后端 25 个 HTTP 接口一一对应地暴露为 MCP 工具
2. 为每个工具提供**语义化描述（description）**——这直接决定 AI 能否正确选用工具
3. 提供标准输入输出（本机）与 HTTP（团队共享）两种接入方式

---

## 快速开始

### 前置条件

- 已运行的 code-gen 后端服务（默认 `http://localhost:6969`）
- Python 3.9+，依赖仅 `requests`
- （可选）Docker，用于团队共享部署

### 1. 启动后端服务

```bash
docker run --name gen --restart=always -p 6969:6969 \
  -v /opt/gen/:/opt/gen/ \
  -v /opt/gen/conf/:/gen/conf/ \
  -v /opt/gen/ext:/gen/ext \
  -d registry.cn-hangzhou.aliyuncs.com/tanghc/gen:latest
```

验证：`curl -X POST http://localhost:6969/type/list -H "Content-Type: application/json" -d '{}'`
返回 `{"code":"0",...}` 即正常。浏览器访问 `http://localhost:6969/` 可用 Web 界面管理模板。

### 2. 部署 MCP 服务器

#### 方式 A：本机直连（推荐个人使用）

MCP 服务器通过标准输入输出与客户端通信，进程由客户端拉起，无需常驻：

```bash
pip install -r requirements.txt
export CODE_GEN_API=http://localhost:6969   # Windows: set CODE_GEN_API=...
python code_gen.py
```

注册到 Claude Code：

```bash
claude mcp add code-gen --transport stdio -- python /绝对路径/code_gen.py
```

#### 方式 B：服务器常驻 HTTP（推荐团队共享）

MCP 服务器以 HTTP 服务常驻，团队共用一套模板与数据源：

直接跑 Python（无需构建镜像）：

```bash
pip install -r requirements.txt

MCP_PORT=6968 CODE_GEN_API=http://127.0.0.1:6969 CODE_GEN_TOKEN=<你的token> \
  nohup python code_gen.py --http >> /var/log/code-gen-mcp.log 2>&1 &
```

或用 Docker 挂载代码目录运行：

```bash
docker run --name code-gen-mcp --restart=always -p 6968:6968 \
  --add-host host.docker.internal:host-gateway \
  -v /opt/code-gen:/app -w /app \
  -e MCP_PORT=6968 \
  -e CODE_GEN_API=http://host.docker.internal:6969 \
  -e CODE_GEN_TOKEN=<你的token> \
  python:3.11-slim \
  sh -c "pip install -q -r requirements.txt && python code_gen.py --http"
```

> 后端与 MCP 同机部署在 Docker 里时，容器内 `127.0.0.1` 指向容器自己，
> 需用 `host.docker.internal` 指向宿主机。

客户端注册：

```bash
claude mcp add code-gen --transport http http://<服务器IP>:6968/mcp
```

验证：

```bash
curl -X POST http://localhost:6968/mcp -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
# 应返回 "serverInfo":{"name":"code-gen-mcp-server"...}
```

---

## 配置

全部通过环境变量注入，Docker 部署时无需改代码。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CODE_GEN_API` | `http://localhost:6969` | 后端 code-gen 服务地址 |
| `MCP_HOST` | `0.0.0.0` | HTTP 模式监听地址 |
| `MCP_PORT` | `6968` | HTTP 模式监听端口 |
| `CODE_GEN_TOKEN` | 空（不鉴权） | HTTP 模式 Bearer Token，设置后需客户端带 `Authorization: Bearer <token>` |
| `CODE_GEN_TIMEOUT` | `15` | 常规接口超时（秒） |
| `CODE_GEN_GENERATE_TIMEOUT` | `120` | 代码生成超时（秒），多表 × 多模板渲染较慢 |

---

## MCP 工具一览

共 **25 个**工具，与后端接口一一对应。

### 数据源（7）

| 工具 | 说明 |
| --- | --- |
| `datasource_dbtypes` | 查询支持的数据库类型（label ↔ dbType） |
| `datasource_test` | 测试连接参数是否可用 |
| `datasource_add` | 新增数据源 |
| `datasource_list` | 列出所有数据源 |
| `datasource_update` | 修改数据源（**全字段覆盖**） |
| `datasource_delete` | 删除数据源（软删除） |
| `datasource_tables` | 查询数据源中的表 |

### 模板（7）

| 工具 | 说明 |
| --- | --- |
| `template_list` | 查询模板列表（可按 groupId 过滤） |
| `template_get` | 查询模板详情 |
| `template_add` | 新增模板 |
| `template_save` | 按「名称 + 分组」新增或更新（已存在则覆盖，适合批量导入） |
| `template_update` | 修改模板 |
| `template_copy` | 复制模板 |
| `template_delete` | 删除模板（软删除） |

### 模板分组（5）

| 工具 | 说明 |
| --- | --- |
| `group_list` / `group_get` | 查询分组 |
| `group_add` / `group_update` | 新增 / 重命名分组 |
| `group_delete` | 删除分组（连带软删除组内模板） |

### 类型映射（3）

| 工具 | 说明 |
| --- | --- |
| `type_list` | 列出数据库类型 → Java 类型映射 |
| `type_get_by_id` | 查询单条映射 |
| `type_update` | 批量修改映射 |

### 代码生成与历史（3）

| 工具 | 说明 |
| --- | --- |
| `generate_code` | **核心**：按表结构 + 模板生成代码 |
| `history_list` | 查询生成历史 |
| `history_delete` | 删除历史记录（物理删除） |

---

## 使用示例

配置好 MCP 后，直接对 AI 说：

> "用 `t_user_order` 表，包名 `com.company.order`，作者 `xiongyu`，
> 按公司规范生成 Entity、Mapper、Service、Controller。"

AI 会自动编排调用：

```
datasource_list        → 拿到数据源 id
datasource_tables(id)  → 确认表名
group_list             → 找到「公司规范」分组
template_list(groupId) → 拿到 4 个模板 id
generate_code(...)     → 返回 4 个文件的完整内容
```

然后把文件落到工程目录。**整个过程无需手写一行 Java，风格与模板完全一致。**

---

## 模板：风格统一的载体

模板使用 [Apache Velocity](https://velocity.apache.org/) 语法。示例（Entity）：

```velocity
## filename=${context.classNamePascal}.java, folder=entity
package ${context.packageName}.entity;

import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

/**
 * ${table.comment} 实体类
 *
 * @author ${context.author}
 * @since ${context.date}
 */
@Data
@TableName("${table.tableName}")
@ApiModel(value = "${context.classNamePascal}对象", description = "${table.comment}")
public class ${context.classNamePascal} implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.ASSIGN_ID)
    @ApiModelProperty("主键ID")
    private Long id;

#foreach($column in $columns)
    @ApiModelProperty("${column.comment}")
    private $column.boxType $column.columnNameLF;

#end
}
```

用什么注解、加不加注释、继承谁、字段顺序——**全部由模板决定，AI 无法偏离**。

首行元信息 `## filename=..., folder=...` 指定输出文件名与目录。
常用变量：`${context.classNamePascal}`、`${context.packageName}`、`${context.author}`、
`${context.date}`、`${table.comment}`、`${columns}`、`${column.boxType}`、`${column.columnNameLF}`。

> 需要现成模板可直接取用：上游仓库的 `templates/` 目录提供了 mybatis-plus、fastmybatis 等模板，
> 可从 <https://gitee.com/durcframework/code-gen> 下载后，通过 `template_save` 导入本服务的模板分组。

---

## 安全须知

⚠️ **部署到公网前请务必注意：**

1. **后端接口默认无鉴权**，且 `/datasource/list` 会返回**数据库明文密码**。
   不要将 6969 端口直接暴露到公网。
2. **MCP 端口建议设置 `CODE_GEN_TOKEN`**，配合防火墙/IP 白名单使用。
3. 建议后端与 MCP 部署在同一内网，仅开放 MCP 端口给受控客户端。

---

## 验证

HTTP 模式下，用一条 JSON-RPC 请求确认服务可用：

```bash
curl -X POST http://localhost:6968/mcp -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

应返回 25 个工具的名称与描述。

本机直连模式下，在 Claude Code 中执行 `/mcp` 命令，确认 `code-gen` 显示为 **Connected**（已连接），
然后直接对 AI 说「列出所有数据源」即可验证链路是否通畅。

---

## 文件说明

```
code_gen.py        # MCP 服务器主程序（支持标准输入输出与 HTTP 两种模式），唯一运行入口
requirements.txt   # 依赖清单（仅需 requests 一个库）
README.md          # 本文档
```

整个服务就是单个 Python 文件，无状态，可任意多实例部署。

---

## 已知问题与限制

- HTTP 模式实现为纯 POST 请求 + JSON 响应，**不支持 SSE（服务端推送）流式响应**，GET 请求返回 405。
  兼容 Claude Code 等主流客户端，但不是完整的 Streamable HTTP 规范实现。
- 后端 `datasource/update` 是**全字段覆盖**，调用前必须先 `datasource_list` 取完整对象。
- 后端业务错误通常仍返回 HTTP 200，错误信息在 JSON 的 `code`/`msg` 中（本 MCP 已转换）。
- 列表接口无分页，模板/历史量很大时响应体会持续增长。
- `history/list` 返回的记录不含 `id` 字段（视后端版本而定），可能导致 `history_delete` 无法定位记录。

---

## 许可证

本项目代码（`code_gen.py`）为独立开发作品，采用 **MIT** 许可证，可自由使用、修改与分发。

本服务仅通过 HTTP 调用上游 [code-gen](https://gitee.com/durcframework/code-gen) 的 REST 接口，
**不包含其任何源代码**。上游同为 MIT 许可证（Copyright 2020 tanghc），在此致谢。

## 相关链接

- 上游项目：<https://gitee.com/durcframework/code-gen>
- MCP 协议：<https://modelcontextprotocol.io>

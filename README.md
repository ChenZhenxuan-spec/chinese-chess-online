# 揭棋 · 双人在线对战

由桌面版 `jieqi_pygame_v1.py` 改造成的 Flask + Flask-SocketIO 网页游戏。房间内两名玩家实时对战，服务器负责洗牌、保存真实身份、验证行棋、处理悔棋与重开。

## 功能

- 创建 6 位房间号、凭房间号加入，红方先行
- WebSocket 实时同步；刷新或短暂断线后凭浏览器本地令牌恢复座位
- 除将帅外 30 枚棋子在服务器安全随机混洗，未翻开身份不会发送到浏览器
- 暗棋按初始位置类型移动，移动后按真实身份移动；控制权始终属于初始位置阵营
- 车、马腿、炮架、兵卒过河、飞将；士可出九宫，象可过河但不可塞象眼
- 合法落点提示、吃子身份公开与图形化展示
- 双方同意后悔棋（恢复明暗状态）或重新洗牌开局

> 房间和断线令牌当前保存在单个服务进程内存中。服务重启或 Render 免费实例休眠重启后，对局会丢失；生产长期运行可再接入 Redis 持久化。

## 本地运行

需要 Python 3.10+。

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

打开 <http://127.0.0.1:5000>。用两个浏览器或一个普通窗口加一个隐私窗口测试双人对战。

运行自动测试：

```bash
python -m unittest discover -s tests -v
```

## Render 部署

仓库已包含 `render.yaml`。部署使用单个 Gunicorn 进程和线程 worker，因为游戏房间目前存在进程内存；多个 worker 会让玩家落在不同状态副本。

1. 将本项目提交并推送到 GitHub/GitLab/Bitbucket 仓库。
2. 登录 [Render Dashboard](https://dashboard.render.com/)，选择 **New → Blueprint**。
3. 连接仓库，Render 会读取 `render.yaml`，确认创建 `jieqi-online` Web Service。
4. 等待健康检查 `/health` 通过，在服务页面取得 `https://…onrender.com` 公网地址。

也可手动创建 Web Service：Build Command 为 `pip install -r requirements.txt`，Start Command 为：

```bash
gunicorn -w 1 --threads 100 -b 0.0.0.0:$PORT app:app
```

`SECRET_KEY` 已在 Blueprint 中配置为自动生成，不要把生产密钥提交到仓库。Render 支持 WebSocket；公网客户端会经同源 HTTPS 自动升级为 WSS。

## 关键协议与安全边界

- `create_room` / `join_room`：建立双人房间并下发随机座位令牌。
- `resume_session`：刷新或 Socket.IO 自动重连后恢复同一座位。
- `select_piece`：服务器校验归属和回合，仅向请求方返回合法落点。
- `move_piece`：服务器再次独立校验坐标、归属、回合和具体棋规。
- `request_action` / `respond_action`：悔棋及重开均须另一方同意。

未翻棋子的 `name`、`color`、随机排列和服务端历史快照从不进入公开状态。

## 健康检查

```text
GET /health
{"status":"ok","rooms":0}
```

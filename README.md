# China A-Share & Fund Analysis Platform

一个可本地运行的 FastAPI Web 应用，提供登录、自选列表、A 股走势分析和基金净值分析。

## Run

```bash
./install.sh
make run
```

一键启动（自动安装缺失依赖并进入前台）：

```bash
make start
```

若要监听所有网卡并使用 80 端口：

```bash
make start80
```

默认地址为 `http://127.0.0.1:8000`。

## Test

```bash
make test
```

## Features

- 注册 / 登录 / 退出
- 自选股票与基金
- A 股日线数据：优先访问 Eastmoney 公共接口
- 基金净值数据：优先解析 Eastmoney 公共页面数据
- 收益、年化收益率、年化波动率、最大回撤、夏普比率与均线
- SQLite 数据层
- 自选代码 CSV 上传导入
- 多资产对比视图
- 可保存筛选条件
- 受保护的 HTML 分析页和 JSON API

## Routes

- `/register`：注册
- `/login`：登录
- `/dashboard`：自选列表
- `/compare?symbols=600519,000001&symbol_type=stock`：多资产对比
- `/compare?symbols=600519,000001&symbol_type=stock&min_annualized_return_pct=0`：带筛选的对比
- `/filters`：保存过的筛选条件
- `/analysis/{stock|fund}/{symbol}`：HTML 分析页
- `/api/analysis/{stock|fund}/{symbol}`：JSON 分析结果
- `/healthz`：健康检查

## Configuration

```bash
DATABASE_URL=sqlite:///data/platform.db
SECRET_KEY=change-this-to-a-long-random-secret
LIVE_DATA_ENABLED=true
REQUEST_TIMEOUT_SECONDS=10
```

生产环境不要使用默认 `SECRET_KEY`。

## Known Limitations

- 无外部数据源连接时，只使用 SQLite 中已导入的数据。
- 本平台的分析结果不构成投资建议。

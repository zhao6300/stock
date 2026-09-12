# China A-Share & Fund Analysis Platform

一个可本地运行的 FastAPI Web 应用，提供登录、自选股、股票走势分析和基金净值分析。

## 运行

```bash
make install
make run
```

默认地址为 `http://127.0.0.1:8000`。

## 测试

```bash
make test
```

## 功能

- 注册 / 登录 / 退出
- 自选股票与基金
- A 股日线数据：优先访问 Eastmoney 公共接口
- 基金净值数据：优先解析 Eastmoney 公共页面数据
- 基础收益、波动率、最大回撤与均线分析
- 本地 CSV 导入，作为网络接口不可用时的数据入口


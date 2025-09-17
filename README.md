# 微信公众号爬虫与分析系统

一个功能完整的微信公众号文章爬取、存储、分析系统，支持防反爬机制、AI智能分析和Web界面操作。

## 🌟 主要特性

- **智能爬取**: 支持搜狗微信搜索，自动获取文章列表和完整内容
- **防反爬系统**: 内置多重反反爬机制，包括UA轮换、智能延迟、代理支持
- **数据存储**: 集成MinIO对象存储，支持大规模数据管理
- **AI分析**: 基于大语言模型的智能文章分析和报告生成
- **Web界面**: FastAPI构建的现代化Web服务
- **定时任务**: 支持定时自动爬取和分析
- **多格式输出**: JSON、Markdown等多种数据格式

## 📁 项目结构

```
sougou/
├── 📄 README.md                    # 项目说明文档
├── 📄 requirements.txt             # Python依赖包
├── 📄 使用说明.md                  # 中文使用说明
├── 📄 防反爬系统使用说明.md        # 防反爬系统详细说明
│
├── 🐍 核心模块
├── 📄 sougou_crawl.py             # 主爬虫模块
├── 📄 fastapi_stream.py           # FastAPI Web服务
├── 📄 anti_crawler.py             # 防反爬系统
├── 📄 minio_storage.py            # MinIO存储模块
├── 📄 optimized_crawl.py          # 优化爬取脚本
│
├── ⚙️ 配置文件
├── 📄 anti_crawler_config.json    # 防反爬配置
├── 📄 wechat_accounts.txt         # 公众号列表配置
│
├── 📊 示例文件
├── 📄 anti_crawler_example.py     # 防反爬使用示例
├── 📄 wechat_*.json               # 爬取结果示例
├── 📄 analysis_report_*.md        # AI分析报告示例
│
└── 📁 数据目录
    ├── 📁 data/                   # 历史爬取数据
    └── 📁 logs/                   # 系统日志
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd sougou

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置设置

#### 2.1 配置公众号列表
编辑 `wechat_accounts.txt` 文件，添加要爬取的公众号名称：

```
证券时报
财经早餐
上交所发布
21世纪经济报道
中国基金报
```

#### 2.2 配置防反爬系统
编辑 `anti_crawler_config.json` 文件：

```json
{
  "max_retries": 5,
  "base_delay": 5.0,
  "max_delay": 15.0,
  "request_limits": {
    "max_requests_per_minute": 15,
    "max_requests_per_hour": 500,
    "concurrent_requests": 1
  }
}
```

#### 2.3 配置MinIO存储
确保MinIO服务运行在 `45.120.102.142:8882`，或修改 `minio_storage.py` 中的连接配置。

### 3. 运行方式

#### 方式1: Web界面（推荐）
```bash
python fastapi_stream.py
```
访问: http://localhost:5001

#### 方式2: 命令行爬取
```bash
python sougou_crawl.py
```

#### 方式3: 优化爬取脚本
```bash
python optimized_crawl.py
```

## 🔧 核心功能

### 1. 智能爬取系统

- **多源搜索**: 支持搜狗微信搜索
- **内容提取**: 自动提取文章标题、摘要、正文、发布时间
- **URL解析**: 自动解析真实微信文章链接
- **批量处理**: 支持批量爬取多个公众号

### 2. 防反爬系统

- **UA轮换**: 自动轮换多种浏览器User-Agent
- **智能延迟**: 基础延迟 + 随机延迟，避免请求过快
- **代理支持**: 支持HTTP/HTTPS代理轮换
- **反爬检测**: 自动检测验证码、IP屏蔽等情况
- **重试机制**: 智能重试策略，提高成功率

### 3. 数据存储系统

- **MinIO集成**: 使用MinIO对象存储管理文章数据
- **多格式支持**: JSON、纯文本等多种存储格式
- **数据检索**: 支持按时间、公众号、关键词检索
- **统计分析**: 提供存储统计和数据分析

### 4. AI分析系统

- **智能分析**: 基于大语言模型的文章内容分析
- **报告生成**: 自动生成结构化的分析报告
- **趋势识别**: 识别市场趋势和热点话题
- **引用标注**: 自动标注信息来源和引用

## 📊 API接口

### Web服务接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 服务首页和API文档 |
| `/crawl` | POST | 爬取指定公众号文章 |
| `/crawl-and-analyze` | POST | 爬取并AI分析文章 |
| `/database/search` | POST | 搜索存储的文章 |
| `/storage/stats` | GET | 获取存储统计信息 |
| `/health` | GET | 健康检查 |

### 请求示例

```bash
# 爬取文章
curl -X POST "http://localhost:5001/crawl" \
  -H "Content-Type: application/json" \
  -d '{"query": "证券时报", "page": 1, "get_real_urls": true, "fetch_content": true}'

# 爬取并分析
curl -X POST "http://localhost:5001/crawl-and-analyze" \
  -H "Content-Type: application/json" \
  -d '{"query": "财经早餐", "page": 1, "save_to_db": true}'
```

## ⚙️ 配置说明

### 防反爬配置

```json
{
  "session_pool_size": 3,           // 会话池大小
  "use_proxy": false,               // 是否使用代理
  "max_retries": 5,                 // 最大重试次数
  "base_delay": 5.0,                // 基础延迟（秒）
  "max_delay": 15.0,                // 最大延迟（秒）
  "enable_ua_rotation": true,       // 启用UA轮换
  "enable_delay_strategy": true,    // 启用延迟策略
  "request_limits": {
    "max_requests_per_minute": 15,  // 每分钟最大请求数
    "max_requests_per_hour": 500,   // 每小时最大请求数
    "concurrent_requests": 1         // 并发请求数
  }
}
```

### 定时任务配置

系统支持定时自动爬取，默认每天早上8:00执行：

```python
# 启动定时任务
scheduled_crawler = ScheduledCrawler(crawler)
scheduled_crawler.schedule_daily_crawl("08:00")
```

## 📈 使用示例

### 1. 基础爬取

```python
from sougou_crawl import WeChatCrawler

# 创建爬虫实例
crawler = WeChatCrawler(use_anti_crawler=True)

# 搜索文章
results = crawler.crawl_and_extract(
    query="证券时报",
    page=1,
    get_real_urls=True,
    fetch_content=True
)

print(f"找到 {len(results['data'])} 篇文章")
```

### 2. 批量爬取

```python
# 爬取所有配置的公众号
results = crawler.crawl_all_configured_accounts(
    get_real_urls=True,
    fetch_content=True
)
```

### 3. 定时爬取

```python
from sougou_crawl import ScheduledCrawler

# 创建定时爬虫
scheduled_crawler = ScheduledCrawler(crawler)

# 立即执行一次定时任务
total_saved = scheduled_crawler.run_daily_crawl_now()
print(f"保存了 {total_saved} 篇文章")
```

## 🔍 数据格式

### 文章数据结构

```json
{
  "title": "文章标题",
  "summary": "文章摘要",
  "source": "公众号名称",
  "publish_time": "2025-09-15 10:30:00",
  "sogou_url": "搜狗搜索结果链接",
  "real_url": "真实微信文章链接",
  "crawl_time": "2025-09-15 14:01:16",
  "success": true,
  "content": "文章完整正文内容",
  "content_fetched": true
}
```

### 分析报告格式

```markdown
# 金融微信公众号文章汇总分析报告 - 2025-09-15

## 一、整体概述
（描述覆盖时间、文章数量、涉及领域）

## 二、主要主题与热点
（1）国内股市概况
1. **主题1**：主题名
   - 主要内容（引用示例：[2][5]）
   - 相关数据与政策细节（引用示例：[2]）

## 三、关键数据与指标
- 宏观经济数据（[4][7]）
- 金融市场数据（[1][6]）

## 四、市场趋势与判断
- 短期趋势（[2][4]）
- 中期趋势（[1][3]）

## 五、机会与风险
- 投资机会（[5][8]）
- 风险提示（[2][7]）

## 六、综合结论
- 总体判断（[全部相关编号]）

## 附录：引用来源说明
[1] 「公众号名称」 : 《文章标题》 - 文章链接
[2] 「公众号名称」 : 《文章标题》 - 文章链接
```

## 🛠️ 故障排除

### 常见问题

1. **文章内容不完整**
   - 原因：微信反爬虫机制
   - 解决：调整防反爬配置，降低请求频率，增加延迟时间

2. **连接超时**
   - 原因：网络不稳定或目标服务器响应慢
   - 解决：增加超时时间，检查网络连接

3. **MinIO连接失败**
   - 原因：MinIO服务未启动或配置错误
   - 解决：检查MinIO服务状态，验证连接配置

4. **验证码问题**
   - 原因：触发反爬机制
   - 解决：暂停爬取，等待一段时间后重试

### 日志查看

```bash
# 查看系统日志
tail -f logs/wechat_analyzer_fastapi.log

# 查看防反爬统计
curl http://localhost:5001/health
```

## 📋 开发计划

- [ ] 支持更多数据源（微博、知乎等）
- [ ] 增加数据可视化功能
- [ ] 优化AI分析算法
- [ ] 添加用户权限管理
- [ ] 支持分布式爬取

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 Issue
- 发送邮件
- 微信群讨论

## 🙏 致谢

感谢以下开源项目的支持：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代Web框架
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML解析
- [MinIO](https://min.io/) - 对象存储
- [LangChain](https://langchain.com/) - AI应用框架

---

**⚠️ 免责声明**: 本项目仅供学习和研究使用，请遵守相关网站的使用条款和robots.txt规则，不要对目标网站造成过大压力。


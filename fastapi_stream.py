#!/usr/bin/env python3
"""
微信公众号文章分析服务 (FastAPI Version)
支持获取指定日期的公众号文章并生成分析报告
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Generator
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import uuid
import logging
from logging.handlers import RotatingFileHandler
import schedule
import threading
import sqlite3
import time
import asyncio

# Assuming sougou_crawl and langchain components are in place
from sougou_crawl import WeChatCrawler, ScheduledCrawler
from langchain_community.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from minio_storage import MinIOArticleStorageAdapter

# --- Basic Setup ---

# 加载环境变量
load_dotenv()


# 配置日志
def setup_logging():
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(
                log_dir / "wechat_analyzer_fastapi.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            ),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )

    # 设置特定模块的日志级别
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("minio").setLevel(logging.WARNING)


# 调用日志设置
setup_logging()

# 创建日志记录器
logger = logging.getLogger(__name__)


# --- Core Logic Classes (Updated for MinIO) ---

class WechatArticleFetcher:
    """获取和存储微信文章的类 (使用MinIO存储)"""

    def __init__(self):
        # 使用MinIO存储
        self.storage = MinIOArticleStorageAdapter()
        self.crawler = WeChatCrawler()
        logger.info("WechatArticleFetcher初始化成功 (MinIO存储)")

    def fetch_articles_by_date(self, curr_date: str, top_k: int = 500) -> List[Dict]:
        """按日期获取文章"""
        try:
            articles = self.storage.get_articles_by_date(curr_date, curr_date, top_k)
            logger.info(f"成功获取 {len(articles)} 篇文章 (日期: {curr_date})")
            return articles
        except Exception as e:
            logger.error(f"获取文章失败: {e}")
            return []

    def save_crawled_articles(self, articles: List[Dict], query_keyword: str = "") -> int:
        """保存爬取的文章到MinIO"""
        # 为文章添加查询关键词
        for article in articles:
            article['query_keyword'] = query_keyword
        
        return self.storage.save_articles(articles)


class WechatAnalyzer:
    """微信公众号文章分析器"""

    def __init__(self):
        # 配置自定义LLM
        os.environ["OPENAI_API_KEY"] = "YOUR_API_KEY"

        self.llm = OpenAI(
            temperature=0,
            openai_api_base="http://45.120.102.120:8990/v1",
            model_name="/mnt/data0/hf_models/models/Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"
        )

        self.fetcher = WechatArticleFetcher()

        # 创建分析提示模板
        self.analysis_prompt = PromptTemplate(
            input_variables=["articles_data"],
            template="""你是一名资深的金融分析师。以下是多篇来自金融领域微信公众号的文章全文，请通读全部内容，并生成一份总体金融信息分析报告。

【任务目标】
- 对所有文章进行整体汇总分析，不逐篇单独列出。
- 提炼共性主题、关键信息与主要趋势。
- 分析市场事件、政策变化、数据指标、机构观点等。
- 提供投资机会与潜在风险分析。
- 摘录到报告中的信息一定尽可能的完整，不要进行简述。
- **一定要在每个关键结论、数据、观点后用 [编号] 标注引用来源编号** - 文章来源编号（article_idx字段），公众号名称（pub_name字段），文章标题（title字段）,文章链接（article_url)切记一定在要在附录里给出。
- 可以合并相似的文字，但是不要简短总结，也不要缩减重要的内容。

【报告格式】参考以下样例
# 金融微信公众号文章汇总分析报告 - 文章发布日期（例如2025-01-01）

## 一、整体概述
（描述覆盖时间、文章数量、涉及领域）

## 二、主要主题与热点
（1）国内股市概况
1. **主题1**：主题名
   - 主要内容（引用示例：[2][5]）
   - 相关数据与政策细节（引用示例：[2]）
2. **主题2**：主题名
   - 内容...
   - 数据...
（2）国内股市板块方面
1. **主题1**：主题名
   - 主要内容（引用示例：[2][5]）
   - 相关数据与政策细节（引用示例：[2]）
2. **主题2**：主题名
   - 内容...
   - 数据...
（3）基金方面
1. **主题1**：主题名
   - 主要内容（引用示例：[2][5]）
   - 相关数据与政策细节（引用示例：[2]）
2. **主题2**：主题名
   - 内容...
   - 数据...
（4）美股方面
1. **主题1**：主题名
   - 主要内容（引用示例：[2][5]）
   - 相关数据与政策细节（引用示例：[2]）
2. **主题2**：主题名
   - 内容...
   - 数据...
（5）国际事件
1. **主题1**：主题名
   - 主要内容（引用示例：[2][5]）
   - 相关数据与政策细节（引用示例：[2]）
2. **主题2**：主题名
   - 内容...
   - 数据...
（6）重要公司公告
1. **主题1**：主题名
   - 主要内容（引用示例：[2][5]）
   - 相关数据与政策细节（引用示例：[2]）
2. **主题2**：主题名
   - 内容...
   - 数据...
（7）其他国内新闻
1. **主题1**：主题名
   - 主要内容（引用示例：[2][5]）
   - 相关数据与政策细节（引用示例：[2]）
2. **主题2**：主题名
   - 内容...
   - 数据...

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

---

## 附录：引用来源说明
[1] 「公众号名称」 : 《文章标题》 - 文章链接
[2] 「公众号名称」 : 《文章标题》 - 文章链接
[3] ...

请分析以下微信公众号文章：
{articles_data}"""
        )

        # 创建分析链
        self.analysis_chain = LLMChain(llm=self.llm, prompt=self.analysis_prompt)

    def analyze_articles_stream_generator(self, date_input: str) -> Generator[str, None, None]:
        """分析指定日期的文章并流式返回结果"""
        standardized_date = date_input

        if not re.match(r'\d{4}-\d{2}-\d{2}', standardized_date):
            error_msg = f"## ❌ 日期格式错误\n\n无法识别日期: {date_input}。请使用YYYY-MM-DD格式。"
            error_event = {
                "event_type": "message_chunk", "thread_id": "error-thread", "agent": "reporter",
                "id": f"run--{str(uuid.uuid4())}", "role": "assistant", "content": error_msg, "finish_reason": "stop"
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            return

        logger.info(f"开始分析日期为 {standardized_date} 的文章")
        articles = self.fetcher.fetch_articles_by_date(standardized_date)

        if not articles:
            error_msg = f"## ❌ 未找到指定日期的文章\n\n未找到日期为 {standardized_date} 的文章。请检查日期是否正确或选择其他日期。"
            error_event = {
                "event_type": "message_chunk", "thread_id": "error-thread", "agent": "reporter",
                "id": f"run--{str(uuid.uuid4())}", "role": "assistant", "content": error_msg, "finish_reason": "stop"
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            return

        articles_text = json.dumps(articles, ensure_ascii=False, indent=2)

        try:
            logger.info("开始调用自定义LLM进行分析")
            result = self.analysis_chain.run(articles_data=articles_text)

            chunk_size = 50
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i + chunk_size]
                if chunk:
                    chunk = chunk.replace("\n", "  \n")
                    event_data = {
                        "event_type": "message_chunk", "thread_id": "93207a48-1bdd-4516-85a2-ef42f82a7605",
                        "agent": "reporter", "id": f"run--{str(uuid.uuid4())}", "role": "assistant", "content": chunk
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    time.sleep(0.05)

            final_event = {
                "event_type": "message_chunk", "thread_id": "93207a48-1bdd-4516-85a2-ef42f82a7605",
                "agent": "reporter", "id": f"run--{str(uuid.uuid4())}", "role": "assistant", "content": "",
                "finish_reason": "stop"
            }
            yield f"data: {json.dumps(final_event)}\n\n"
            logger.info("文章分析完成")

        except Exception as e:
            logger.error(f"分析过程中出现错误: {e}")
            error_event = {
                "event_type": "message_chunk", "thread_id": "error-thread", "agent": "reporter",
                "id": f"run--{str(uuid.uuid4())}", "role": "assistant", "content": f"❌ 分析过程中出现错误: {str(e)}",
                "finish_reason": "stop"
            }
            yield f"data: {json.dumps(error_event)}\n\n"


# --- 定时任务 ---
class EnhancedScheduledCrawler(ScheduledCrawler):
    def __init__(self, crawler: WeChatCrawler, fetcher: WechatArticleFetcher):
        super().__init__(crawler)
        self.fetcher = fetcher

    def schedule_daily_crawl_with_save(self, time_str: str = "08:00"):
        """设置每日早上8点定时爬取（爬取前一天下午3点到今天早上8点的内容）并保存到MinIO"""
        def job():
            self.logger.info("开始每日定时爬取任务")
            
            # 计算时间范围：前一天下午3点到今天早上8点
            now = datetime.now()
            today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
            yesterday_3pm = (now - timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
            
            self.logger.info(f"爬取时间范围: {yesterday_3pm.strftime('%Y-%m-%d %H:%M:%S')} 到 {today_8am.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 获取配置的公众号列表
            accounts = self.crawler.load_wechat_accounts()
            
            if not accounts:
                self.logger.warning("没有配置任何公众号，跳过定时任务")
                return
            
            # 为每个公众号单独爬取和保存
            total_articles_saved = 0
            date_str = now.strftime('%Y_%m%d')  # 格式：2025_0905
            
            for account in accounts:
                try:
                    self.logger.info(f"开始爬取公众号: {account}")
                    
                    # 爬取单个公众号的文章
                    results = self.crawler.crawl_and_extract(
                        query=account,
                        page=1,
                        get_real_urls=True,
                        fetch_content=True,
                        start_time=yesterday_3pm,
                        end_time=today_8am
                    )
                    
                    if results['success'] and results['data']:
                        # 保存到MinIO数据库
                        saved_count = self.fetcher.save_crawled_articles(results['data'], account)
                        
                        # 如果有文章，也保存到单独的文件
                        filename = f'wechat_{account}_{date_str}.json'
                        # 清理文件名中的特殊字符
                        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                        
                        self.crawler.save_results(results, filename)
                        
                        article_count = len(results['data'])
                        total_articles_saved += article_count
                        
                        self.logger.info(f"公众号 '{account}' 爬取完成: {article_count} 篇文章已保存到 {filename} 和MinIO数据库")
                    else:
                        self.logger.info(f"公众号 '{account}' 在指定时间段内没有发布文章")
                        
                except Exception as e:
                    self.logger.error(f"爬取公众号 '{account}' 时发生错误: {e}")
                    continue
                
                # 添加延时避免请求过快
                time.sleep(2)
            
            self.logger.info(f"每日定时任务完成: 共处理 {len(accounts)} 个公众号，保存 {total_articles_saved} 篇文章")
        
        # 设置每日定时任务
        schedule.every().day.at(time_str).do(job)
        self.logger.info(f"已设置每日定时任务: 每天{time_str}爬取所有配置的公众号（前一天15:00到当天08:00的内容）并保存到MinIO")

    def run_daily_crawl_now(self):
        """立即执行每日爬取任务（用于测试）并保存到MinIO"""
        self.logger.info("手动触发每日爬取任务")
        
        # 计算时间范围：前一天下午3点到今天早上8点
        now = datetime.now()
        today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
        yesterday_3pm = (now - timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
        
        self.logger.info(f"爬取时间范围: {yesterday_3pm.strftime('%Y-%m-%d %H:%M:%S')} 到 {today_8am.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 获取配置的公众号列表
        accounts = self.crawler.load_wechat_accounts()
        
        if not accounts:
            self.logger.warning("没有配置任何公众号，跳过爬取任务")
            return 0
        
        # 为每个公众号单独爬取和保存
        total_articles_saved = 0
        date_str = now.strftime('%Y_%m%d')  # 格式：2025_0905
        
        for account in accounts:
            try:
                self.logger.info(f"开始爬取公众号: {account}")
                
                # 爬取单个公众号的文章
                results = self.crawler.crawl_and_extract(
                    query=account,
                    page=1,
                    get_real_urls=True,
                    fetch_content=True,
                    start_time=yesterday_3pm,
                    end_time=today_8am
                )
                
                if results['success'] and results['data']:
                    # 保存到MinIO数据库
                    saved_count = self.fetcher.save_crawled_articles(results['data'], account)
                    
                    # 如果有文章，也保存到单独的文件
                    filename = f'wechat_{account}_{date_str}.json'
                    # 清理文件名中的特殊字符
                    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                    
                    self.crawler.save_results(results, filename)
                    
                    article_count = len(results['data'])
                    total_articles_saved += article_count
                    
                    self.logger.info(f"公众号 '{account}' 爬取完成: {article_count} 篇文章已保存到 {filename} 和MinIO数据库")
                else:
                    self.logger.info(f"公众号 '{account}' 在指定时间段内没有发布文章")
                    
            except Exception as e:
                self.logger.error(f"爬取公众号 '{account}' 时发生错误: {e}")
                continue
            
            # 添加延时避免请求过快
            time.sleep(2)
        
        self.logger.info(f"手动爬取任务完成: 共处理 {len(accounts)} 个公众号，保存 {total_articles_saved} 篇文章")
        return total_articles_saved


def run_scheduler():
    """Continuously run the scheduler."""
    while True:
        schedule.run_pending()
        time.sleep(1)


# --- FastAPI Application ---

# 创建FastAPI应用
app = FastAPI(
    title="微信公众号文章分析服务",
    description="支持获取、搜索和分析微信公众号文章"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应配置为特定来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化分析器和爬虫
analyzer = WechatAnalyzer()
crawler = WeChatCrawler()
scheduled_crawler = EnhancedScheduledCrawler(crawler, analyzer.fetcher)
scheduled_tasks = []


# --- Pydantic Models for Request Bodies ---

class AnalyzeRequest(BaseModel):
    date: str = Field(..., description="要分析的日期，格式为 YYYY-MM-DD")


class SearchRequest(BaseModel):
    query: str
    page: int = 1
    get_real_urls: bool = False
    fetch_content: bool = False
    save_to_db: bool = False


class DailyScheduleRequest(BaseModel):
    time_str: str = "08:00"


class CrawlAnalyzeRequest(BaseModel):
    query: str
    page: int = 1
    save_to_db: bool = True


class DbSearchRequest(BaseModel):
    keyword: Optional[str] = None
    date: Optional[str] = None
    limit: int = 100


# --- FastAPI Endpoints ---

@app.on_event("startup")
async def startup_event():
    """Start the background scheduler thread on application startup."""
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("定时任务调度器已启动")


@app.post('/analyze')
async def analyze_articles_endpoint(req: AnalyzeRequest):
    """分析指定日期的文章并流式返回结果"""
    logger.info(f"收到分析请求，日期: {req.date}")
    return StreamingResponse(
        analyzer.analyze_articles_stream_generator(req.date),
        media_type='text/event-stream'
    )


@app.post('/search')
async def search_wechat_articles(req: SearchRequest):
    """搜索微信公众号文章"""
    logger.info(f"收到搜索请求: {req.dict()}")
    try:
        results = crawler.crawl_and_extract(req.query, req.page, req.get_real_urls, req.fetch_content)
        if req.save_to_db and results.get('success') and results.get('data'):
            saved_count = analyzer.fetcher.save_crawled_articles(results['data'], req.query)
            results['db_saved'] = saved_count
            results['message'] += f"，已保存 {saved_count} 篇到数据库"
        return results
    except Exception as e:
        logger.error(f"处理搜索请求时发生错误: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@app.get('/schedule')
async def get_scheduled_tasks():
    """获取所有定时任务"""
    return {
        "success": True,
        "tasks": scheduled_tasks,
        "scheduler_running": any(isinstance(t, threading.Thread) and t.is_alive() for t in threading.enumerate())
    }


@app.post('/schedule/daily')
async def schedule_daily_crawl(req: DailyScheduleRequest):
    """设置每日定时爬取任务（爬取前一天下午3点到今天早上8点的内容）"""
    logger.info(f"设置每日定时任务: {req.dict()}")
    try:
        scheduled_crawler.schedule_daily_crawl_with_save(req.time_str)
        task_info = {
            "type": "daily_crawl",
            "time": req.time_str,
            "description": f"每天{req.time_str}爬取所有配置的公众号（前一天15:00到当天08:00的内容）",
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        scheduled_tasks.append(task_info)
        return {
            "success": True,
            "message": f"成功设置每日定时任务: 每天{req.time_str}爬取所有配置的公众号并保存到MinIO和本地文件",
            "task": task_info
        }
    except Exception as e:
        logger.error(f"设置每日定时任务时发生错误: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@app.post('/crawl-and-analyze')
async def crawl_and_analyze(req: CrawlAnalyzeRequest):
    """爬取文章并直接进行AI分析"""
    logger.info(f"开始爬取并分析，查询: {req.query}")

    def generate_analysis():
        crawl_results = crawler.crawl_and_extract(req.query, req.page, get_real_urls=True, fetch_content=True)

        if not crawl_results.get('success') or not crawl_results.get('data'):
            error_event = {"event_type": "error", "content": "未找到相关文章"}
            yield f"data: {json.dumps(error_event)}\n\n"
            return

        if req.save_to_db:
            saved_count = analyzer.fetcher.save_crawled_articles(crawl_results['data'], req.query)
            logger.info(f"已保存 {saved_count} 篇文章到数据库")

        articles_for_analysis = [
            {
                "article_idx": i, "title": article['title'], "summary_content": article['summary'],
                "pub_name": article['source'],
                "publish_date": article['publish_time'][:10] if article.get('publish_time') else "",
                "article_url": article.get('real_url') or article.get('sogou_url'),
            } for i, article in enumerate(crawl_results['data'], 1)
        ]

        articles_text = json.dumps(articles_for_analysis, ensure_ascii=False, indent=2)

        try:
            logger.info("开始AI分析爬取的文章")
            result = analyzer.analysis_chain.run(articles_data=articles_text)

            chunk_size = 50
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i + chunk_size]
                if chunk:
                    chunk = chunk.replace("\n", "  \n")
                    event_data = {
                        "event_type": "message_chunk", "thread_id": "crawl-analysis", "agent": "crawler_analyzer",
                        "id": f"run--{str(uuid.uuid4())}", "role": "assistant", "content": chunk,
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    time.sleep(0.05)

            final_event = {
                "event_type": "message_chunk", "thread_id": "crawl-analysis", "agent": "crawler_analyzer",
                "id": f"run--{str(uuid.uuid4())}", "role": "assistant", "content": "", "finish_reason": "stop"
            }
            yield f"data: {json.dumps(final_event)}\n\n"
            logger.info("爬取文章分析完成")
        except Exception as e:
            logger.error(f"分析过程中出现错误: {e}")
            error_event = {
                "event_type": "error", "content": f"分析过程中出现错误: {e}", "finish_reason": "stop"
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(generate_analysis(), media_type="text/event-stream")


@app.post('/database/search')
async def search_database(req: DbSearchRequest):
    """搜索MinIO存储中的文章"""
    try:
        if req.keyword:
            articles = analyzer.fetcher.storage.search_articles(query=req.keyword, limit=req.limit)
            logger.info(f"根据关键词 '{req.keyword}' 搜索到 {len(articles)} 篇文章")
        elif req.date:
            articles = analyzer.fetcher.storage.get_articles_by_date(req.date, req.date, req.limit)
            logger.info(f"根据日期 '{req.date}' 搜索到 {len(articles)} 篇文章")
        else:
            raise HTTPException(status_code=400, detail="请提供关键词或日期参数")

        return {"success": True, "count": len(articles), "articles": articles}
    except Exception as e:
        logger.error(f"搜索数据库时发生错误: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@app.get('/storage/stats')
async def get_storage_stats():
    """获取MinIO存储统计信息"""
    try:
        stats = analyzer.fetcher.storage.get_article_stats()
        logger.info(f"获取存储统计信息: {stats}")
        return {
            "success": True,
            "storage_type": "MinIO",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"获取存储统计信息失败: {e}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")


@app.get('/health')
async def health_check():
    """健康检查端点 (增强版 - 检查MinIO连接)"""
    try:
        # 检查MinIO连接
        stats = analyzer.fetcher.storage.get_article_stats()
        logger.info("健康检查请求 - MinIO连接正常")
        return {
            "status": "healthy",
            "storage": "MinIO",
            "message": "微信公众号文章分析服务运行正常",
            "timestamp": datetime.now().isoformat(),
            "article_count": stats.get("total_articles", 0),
            "storage_size_mb": stats.get("total_size_mb", 0)
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get('/', response_class=HTMLResponse)
async def index():
    """返回简单的使用说明"""
    logger.info("根路径访问")
    return """
    <h1>微信公众号文章分析服务 (FastAPI Version with MinIO)</h1>
    <p>API文档请访问 <a href="/docs">/docs</a> 或 <a href="/redoc">/redoc</a>.</p>
    <h2>可用接口:</h2>
    <ul>
        <li><strong>POST /analyze</strong> - 分析指定日期的文章</li>
        <li><strong>POST /search</strong> - 搜索微信公众号文章</li>
        <li><strong>GET /schedule</strong> - 查看定时任务列表</li>
        <li><strong>POST /schedule/daily</strong> - 设置每日定时爬取任务（每天8点爬取前一天15:00到当天08:00的内容）</li>
        <li><strong>POST /crawl-and-analyze</strong> - 爬取文章并直接AI分析</li>
        <li><strong>POST /database/search</strong> - 搜索MinIO存储中的文章</li>
        <li><strong>GET /storage/stats</strong> - 获取MinIO存储统计信息</li>
        <li><strong>GET /health</strong> - 健康检查 (包含MinIO连接状态)</li>
    </ul>
    """


if __name__ == '__main__':
    import uvicorn

    logger.info("启动微信公众号文章分析服务 (FastAPI)")
    # 使用 uvicorn 启动服务
    # host="0.0.0.0" 监听所有网络接口
    # port=5001 指定端口
    # reload=True 开启热重载，方便开发
    uvicorn.run("fastapi_stream:app", host='0.0.0.0', port=5001, reload=True)
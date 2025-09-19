import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import json
import os
import time
import random
import schedule
from typing import List, Dict, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import logging
from minio_storage import MinIOArticleStorage
from anti_crawler import create_anti_crawler_session


@dataclass
class WeChatArticle:
    """微信文章数据结构"""
    title: str = ""
    summary: str = ""
    source: str = ""
    publish_time: str = ""
    sogou_url: str = ""
    real_url: str = ""
    crawl_time: str = ""
    success: bool = False
    content: str = ""  # 文章正文内容（纯文本）
    content_fetched: bool = False  # 是否成功获取内容

class WeChatCrawler:
    """微信公众号爬虫类 - 封装用于FastAPI集成"""
    
    def __init__(self, config_file: str = "wechat_accounts.txt", use_anti_crawler: bool = True):
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 初始化防反爬系统
        self.use_anti_crawler = use_anti_crawler
        
        # 始终保留headers属性，用于兼容性
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        
        if self.use_anti_crawler:
            self.anti_crawler_session = create_anti_crawler_session(use_proxy=False, max_retries=3)
            self.logger.info("防反爬系统初始化完成")
        else:
            self.logger.info("使用传统请求方式")
        
        # 初始化MinIO存储
        self.storage = MinIOArticleStorage()
        self.logger.info("MinIO存储初始化完成")
        
        # 配置文件路径
        self.config_file = config_file
        
        
    def load_wechat_accounts(self) -> List[str]:
        """从配置文件加载微信公众号列表"""
        accounts = []
        try:
            if not os.path.exists(self.config_file):
                self.logger.warning(f"配置文件 {self.config_file} 不存在，使用默认配置")
                return [
                    "中金所发布",
                    "上交所发布", 
                    "李迅雷金融与投资",
                    "量子位",
                    "机器之心",
                    "证券时报",
                    "财经早餐",
                    "畅游股海的老船长",
                    "索策略",
                    "财天早知道",
                    "证监会发布",
                    "中证协发布",
                    "中国基金报",
                    "蓝洞新消费",
                    "上海证券报",
                    "21世纪经济报道",
                    "券商中国",
                    "中国证券报",
                    "阿尔法工场研究院",
                    "金石杂谈",
                    "宏策股",
                    "180K",
                    "证券时报财富资讯",
                    "韭研公社",
                    "表舅是养基大户",
                    "远川研究所",
                    "格上财富",
                    "真是港股圈",
                    "华尔街见闻",
                    "寻瑕记"
                ]
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    # 跳过空行和注释行
                    if line and not line.startswith('#'):
                        accounts.append(line)
                        
            if accounts:
                self.logger.info(f"从配置文件加载了 {len(accounts)} 个公众号: {accounts}")
            else:
                self.logger.warning("配置文件为空，使用默认配置")
                accounts = [
                    "中金所发布",
                    "上交所发布", 
                    "李迅雷金融与投资",
                    "量子位",
                    "机器之心",
                    "证券时报",
                    "财经早餐",
                    "畅游股海的老船长",
                    "索策略",
                    "财天早知道",
                    "证监会发布",
                    "中证协发布",
                    "中国基金报",
                    "蓝洞新消费",
                    "上海证券报",
                    "21世纪经济报道",
                    "券商中国",
                    "中国证券报",
                    "阿尔法工场研究院",
                    "金石杂谈",
                    "宏策股",
                    "180K",
                    "证券时报财富资讯",
                    "韭研公社",
                    "表舅是养基大户",
                    "远川研究所",
                    "格上财富",
                    "真是港股圈",
                    "华尔街见闻",
                    "寻瑕记"
                ]
                
        except Exception as e:
            self.logger.error(f"读取配置文件失败: {e}，使用默认配置")
            accounts = [
                "中金所发布",
                "上交所发布", 
                "李迅雷金融与投资",
                "量子位",
                "机器之心",
                "证券时报",
                "财经早餐",
                "畅游股海的老船长",
                "索策略",
                "财天早知道",
                "证监会发布",
                "中证协发布",
                "中国基金报",
                "蓝洞新消费",
                "上海证券报",
                "21世纪经济报道",
                "券商中国",
                "中国证券报",
                "阿尔法工场研究院",
                "金石杂谈",
                "宏策股",
                "180K",
                "证券时报财富资讯",
                "韭研公社",
                "表舅是养基大户",
                "远川研究所",
                "格上财富",
                "真是港股圈",
                "华尔街见闻",
                "寻瑕记"
            ]
            
        return accounts
    
    def save_wechat_accounts(self, accounts: List[str]) -> bool:
        """保存公众号列表到配置文件（简化版，仅用于初始化）"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write("# 微信公众号配置文件\n")
                f.write("# 每行一个公众号名称，支持#号注释\n\n")
                
                for account in accounts:
                    f.write(f"{account}\n")
                    
            self.logger.info(f"已保存 {len(accounts)} 个公众号到配置文件")
            return True
            
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {e}")
            return False
    
    def extract_real_url(self, response_text: str) -> Optional[str]:
        """从搜狗微信重定向页面的JavaScript中提取真实的微信文章URL"""
        # 使用正则表达式匹配JavaScript中的URL构建部分
        url_pattern = r"url \+= '([^']+)';"
        matches = re.findall(url_pattern, response_text)
        
        if matches:
            # 将所有匹配的部分拼接成完整URL
            real_url = ''.join(matches)
            return real_url
        
        # 备用方法：直接匹配完整的URL模式
        full_url_pattern = r'https://mp\.weixin\.qq\.com/s\?[^"\']* '
        full_match = re.search(full_url_pattern, response_text)
        if full_match:
            return full_match.group(0)
        
        return None
    
    def get_real_wechat_url(self, sogou_url: str) -> Optional[str]:
        """获取搜狗微信链接对应的真实微信文章URL"""
        try:
            if self.use_anti_crawler:
                response = self.anti_crawler_session.get(sogou_url, timeout=10)
            else:
                response = requests.get(sogou_url, headers=self.headers, timeout=10)
            
            response.raise_for_status()
            real_url = self.extract_real_url(response.text)
            if real_url:
                self.logger.info(f"成功提取真实URL: {real_url[:100]}...")
                return real_url
            else:
                self.logger.warning(f"未能提取到真实URL: {sogou_url[:100]}...")
                return None
                
        except requests.RequestException as e:
            self.logger.error(f"请求失败: {e}")
            return None
    
    def extract_article_text(self, html_content: str) -> str:
        """从HTML中提取文章正文内容"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 移除脚本和样式标签
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 尝试多种选择器来定位文章正文
        content_selectors = [
            '#js_content',  # 微信文章主要内容区域
            '.rich_media_content',  # 微信文章内容
            '.article-content',
            '.content',
            'article',
            '.post-content'
        ]
        
        content_text = ""
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # 获取文本内容并清理
                content_text = content_elem.get_text(separator='\n', strip=True)
                break
        
        # 如果没有找到特定的内容区域，使用body标签
        if not content_text:
            body = soup.find('body')
            if body:
                content_text = body.get_text(separator='\n', strip=True)
        
        # 清理文本：移除多余的空行和空格
        lines = [line.strip() for line in content_text.split('\n') if line.strip()]
        clean_content = '\n'.join(lines)
        
        return clean_content
    
    def fetch_article_content(self, real_url: str, title: str = "") -> Dict[str, str]:
        """获取微信文章的正文内容"""
        try:
            if self.use_anti_crawler:
                # 使用防反爬系统
                response = self.anti_crawler_session.get(real_url, timeout=15)
            else:
                # 为微信文章设置特殊的请求头
                wechat_headers = self.headers.copy()
                wechat_headers.update({
                    "Referer": "https://weixin.sogou.com/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                })
                response = requests.get(real_url, headers=wechat_headers, timeout=15)
            
            response.raise_for_status()
            
            # 提取正文内容
            content_text = self.extract_article_text(response.text)
            
            if content_text:
                self.logger.info(f"成功提取文章正文内容，长度: {len(content_text)} 字符")
                return {
                    "content": content_text,
                    "success": True
                }
            else:
                self.logger.warning("未能提取到有效的文章内容")
                return {
                    "content": "",
                    "success": False
                }
            
        except requests.RequestException as e:
            self.logger.error(f"获取文章内容失败: {e}")
            return {
                "content": "",
                "success": False
            }
        except Exception as e:
            self.logger.error(f"提取文章内容失败: {e}")
            return {
                "content": "",
                "success": False
            }
    
    def search_articles(self, query: str, page: int = 1, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[WeChatArticle]:
        """搜索微信文章"""
        
        url = "https://weixin.sogou.com/weixin"
        params = {
            "query": query,
            "_sug_type_": "",
            "s_from": "input",
            "_sug_": "y",
            "type": "2",
            "page": str(page),
            "ie": "utf8"
        }
        
        # 增强请求头
        enhanced_headers = self.headers.copy()
        enhanced_headers.update({
            "Accept-Encoding": "gzip, deflate, br",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "max-age=0",
            "Referer": "https://weixin.sogou.com/"
        })
        
        try:
            if self.use_anti_crawler:
                # 使用防反爬系统
                # 先访问首页建立会话
                self.anti_crawler_session.get("https://weixin.sogou.com/", timeout=10)
                time.sleep(random.uniform(2, 4))  # 随机延迟
                
                response = self.anti_crawler_session.get(url, params=params, timeout=15)
            else:
                # 先访问首页建立会话
                requests.get("https://weixin.sogou.com/", headers=enhanced_headers, timeout=10)
                time.sleep(random.uniform(2, 4))  # 随机延迟
                
                response = requests.get(url, headers=enhanced_headers, params=params, timeout=15)
            
            
            # 获取cookies 更新到 headers（仅在不使用防反爬系统时）
            if not self.use_anti_crawler and response.cookies:
                cookies_str = '; '.join([f"{key}={value}" for key, value in response.cookies.items()])
                self.headers['Cookie'] = cookies_str
            response.raise_for_status()
            
            articles = self._parse_search_results(response.text, query)
            
            # 如果指定了时间范围，进行过滤
            if start_time or end_time:
                articles = self._filter_articles_by_time(articles, start_time, end_time)
            
            self.logger.info(f"搜索 '{query}' 第{page}页，找到 {len(articles)} 篇文章")
            return articles
            
        except requests.RequestException as e:
            self.logger.error(f"搜索请求失败: {e}")
            return []
    
    def _parse_search_results(self, html_content: str, query: str) -> List[WeChatArticle]:
        """解析搜索结果页面"""
        soup = BeautifulSoup(html_content, 'html.parser')
        articles = []
        
        # 精准定位：搜狗微信搜索结果在 ul.news-list 下的 li 元素中
        news_items = soup.select('ul.news-list li')
        
        for item in news_items:
            article = WeChatArticle()
            article.crawl_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 1. 提取标题
            title_elem = item.select_one('h3 a')
            if title_elem:
                article.title = title_elem.get_text(strip=True)
            else:
                title_elem = item.select_one('h3')
                if title_elem:
                    article.title = title_elem.get_text(strip=True)
            
            if not article.title:
                continue
            
            # 2. 提取简要
            summary_elems = item.select('p')
            for p_elem in summary_elems:
                text = p_elem.get_text(strip=True)
                if (len(text) > 20 and 
                    not re.search(r'\d{4}-\d{1,2}-\d{1,2}', text) and
                    not re.search(r'今日|昨日|\d+小时前|\d+分钟前', text) and
                    '微信公众平台' not in text):
                    article.summary = text[:300] + '...' if len(text) > 300 else text
                    break
            
            # 3. 提取搜狗链接
            link_elem = item.select_one('h3 a')
            if link_elem:
                href = link_elem.get('href', '')
                if href:
                    if href.startswith('/'):
                        article.sogou_url = 'https://weixin.sogou.com' + href
                    else:
                        article.sogou_url = href
            
            # 4. 提取来源
            source_elem = item.select_one('div.s-p span.all-time-y2')
            if source_elem:
                source_text = source_elem.get_text(strip=True)
                if source_text and source_text != '微信公众平台':
                    article.source = source_text
            
            # 5. 提取时间
            time_script_elem = item.select_one('div.s-p span.s2 script')
            if time_script_elem:
                script_text = time_script_elem.get_text()
                timestamp_match = re.search(r'timeConvert\(\'(\d+)\'\)', script_text)
                if timestamp_match:
                    timestamp = int(timestamp_match.group(1))
                    article.publish_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            articles.append(article)
        
        return articles
    
    def _filter_articles_by_time(self, articles: List[WeChatArticle], start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[WeChatArticle]:
        """根据时间范围过滤文章"""
        if not start_time and not end_time:
            return articles
        
        filtered_articles = []
        
        for article in articles:
            if not article.publish_time:
                continue
                
            try:
                # 解析文章发布时间
                article_time = datetime.strptime(article.publish_time, '%Y-%m-%d %H:%M:%S')
                
                # 检查是否在时间范围内
                in_range = True
                
                if start_time and article_time < start_time:
                    in_range = False
                    
                if end_time and article_time > end_time:
                    in_range = False
                
                if in_range:
                    filtered_articles.append(article)
                    
            except (ValueError, TypeError) as e:
                self.logger.warning(f"无法解析文章时间: {article.publish_time}, 错误: {e}")
                continue
        
        self.logger.info(f"时间过滤：原文章 {len(articles)} 篇，过滤后 {len(filtered_articles)} 篇")
        return filtered_articles
    
    def get_real_urls_batch(self, articles: List[WeChatArticle], max_workers: int = 3) -> List[WeChatArticle]:
        """批量获取真实URL"""
        def process_article(article: WeChatArticle) -> WeChatArticle:
            if article.sogou_url:
                real_url = self.get_real_wechat_url(article.sogou_url)
                if real_url:
                    article.real_url = real_url
                    article.success = True
                else:
                    article.success = False
                # 添加延时避免请求过快
                time.sleep(1)
            return article
        
        self.logger.info(f"开始批量获取 {len(articles)} 篇文章的真实URL...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            processed_articles = list(executor.map(process_article, articles))
        
        successful_count = sum(1 for article in processed_articles if article.success)
        self.logger.info(f"批量处理完成，成功获取 {successful_count}/{len(articles)} 个真实URL")
        
        return processed_articles
    
    def save_article_to_storage(self, article: WeChatArticle) -> bool:
        """保存文章到MinIO存储"""
        try:
            # 转换为字典格式以兼容MinIO存储
            article_dict = {
                "title": article.title,
                "summary": article.summary,
                "source": article.source,
                "publish_time": article.publish_time,
                "sogou_url": article.sogou_url,
                "real_url": article.real_url,
                "content": article.content,
                "crawl_time": article.crawl_time,
                "success": article.success,
                "content_fetched": article.content_fetched
            }
            
            # 使用MinIO存储保存单篇文章
            success = self.storage.save_article(article_dict)
            
            if success:
                self.logger.info(f"文章已保存到MinIO: {article.title[:30]}...")
                return True
            else:
                self.logger.warning(f"文章可能重复，未保存: {article.title[:30]}...")
                return False
            
        except Exception as e:
            self.logger.error(f"保存文章到MinIO失败: {e}")
            return False
    
    def fetch_contents_batch(self, articles: List[WeChatArticle], max_workers: int = 2) -> List[WeChatArticle]:
        """批量获取文章正文内容并保存到数据库"""
        def fetch_content(article: WeChatArticle) -> WeChatArticle:
            if article.real_url and article.success:
                content_result = self.fetch_article_content(article.real_url, article.title)
                article.content = content_result["content"]
                article.content_fetched = content_result["success"]
                
                # 保存到MinIO存储
                if article.content_fetched:
                    storage_success = self.save_article_to_storage(article)
                    if storage_success:
                        self.logger.info(f"文章已保存到MinIO存储: {article.title[:30]}...")
                
                # 添加延时避免请求过快
                time.sleep(2)
            return article
        
        # 只处理成功获取真实URL的文章
        valid_articles = [article for article in articles if article.success and article.real_url]
        
        if not valid_articles:
            self.logger.warning("没有有效的文章URL可以获取内容")
            return articles
        
        self.logger.info(f"开始批量获取 {len(valid_articles)} 篇文章的正文内容...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 只处理有效文章
            processed_valid = list(executor.map(fetch_content, valid_articles))
        
        # 更新原始列表中的对应文章
        valid_dict = {id(article): article for article in processed_valid}
        for i, article in enumerate(articles):
            if id(article) in valid_dict:
                articles[i] = valid_dict[id(article)]
        
        successful_content_count = sum(1 for article in articles if article.content_fetched)
        self.logger.info(f"内容获取完成，成功获取 {successful_content_count}/{len(valid_articles)} 篇文章内容")
        
        return articles
    
    def crawl_and_extract(self, query: str, page: int = 1, get_real_urls: bool = True, fetch_content: bool = False, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> Dict:
        """完整的爬取和提取流程"""
        start_time_exec = time.time()
        
        # 1. 搜索文章
        articles = self.search_articles(query, page, start_time, end_time)
        
        if not articles:
            return {
                "success": False,
                "message": "未找到相关文章",
                "data": [],
                "stats": {"total": 0, "real_urls_extracted": 0, "content_fetched": 0, "duration": 0}
            }
        
        # 2. 获取真实URL（可选）
        if get_real_urls:
            articles = self.get_real_urls_batch(articles)
        
        # 3. 获取完整内容（可选）
        if fetch_content and get_real_urls:
            articles = self.fetch_contents_batch(articles)
        
        # 4. 统计结果
        total_articles = len(articles)
        successful_extractions = sum(1 for article in articles if article.success)
        content_fetched_count = sum(1 for article in articles if article.content_fetched)
        duration = time.time() - start_time_exec
        
        # 5. 转换为字典格式
        articles_data = []
        for article in articles:
            articles_data.append({
                "title": article.title,
                "summary": article.summary,
                "source": article.source,
                "publish_time": article.publish_time,
                "sogou_url": article.sogou_url,
                "real_url": article.real_url,
                "crawl_time": article.crawl_time,
                "success": article.success,
                "content": article.content[:200] + "..." if len(article.content) > 200 else article.content,  # 只显示前200字符
                "content_fetched": article.content_fetched
            })
        
        return {
            "success": True,
            "message": f"成功爬取 {total_articles} 篇文章" + (f"，获取 {content_fetched_count} 篇完整内容" if fetch_content else ""),
            "data": articles_data,
            "stats": {
                "total": total_articles,
                "real_urls_extracted": successful_extractions,
                "content_fetched": content_fetched_count,
                "duration": round(duration, 2),
                "query": query,
                "page": page
            }
        }
    
    def crawl_all_configured_accounts(
        self,
        get_real_urls: bool = True,
        fetch_content: bool = False,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """
        爬取所有配置文件中的公众号（简化版）
        """
        accounts = self.load_wechat_accounts()
        
        if not accounts:
            return {
                "success": False,
                "message": "没有配置任何公众号",
                "data": [],
                "stats": {"queries": 0, "total_found": 0}
            }
        
        self.logger.info(f"开始爬取配置文件中的 {len(accounts)} 个公众号")
        
        all_articles = []
        total_articles = 0
        
        for i, account in enumerate(accounts, 1):
            self.logger.info(f"[{i}/{len(accounts)}] 正在爬取公众号：{account}")
            
            try:
                result = self.crawl_and_extract(
                    query=account,
                    page=1,
                    get_real_urls=get_real_urls,
                    fetch_content=fetch_content,
                    start_time=start_time,
                    end_time=end_time
                )
                
                if result['success']:
                    all_articles.extend(result['data'])
                    total_articles += len(result['data'])
                    self.logger.info(f"公众号 '{account}' 爬取成功：{len(result['data'])} 篇文章")
                else:
                    self.logger.error(f"公众号 '{account}' 爬取失败：{result.get('error', '未知错误')}")
                
                # 添加延迟避免请求过快
                if i < len(accounts):
                    time.sleep(2)
                    
            except Exception as e:
                self.logger.error(f"爬取公众号 '{account}' 时发生异常：{e}")
                continue
        
        return {
            'success': True,
            'data': all_articles,
            'stats': {
                'queries': len(accounts),
                'total_found': total_articles,
                'timestamp': datetime.now().isoformat()
            }
        }

    def get_articles_from_storage(self, limit: int = None) -> List[Dict]:
        """从MinIO存储获取文章"""
        try:
            # 使用MinIO存储搜索文章
            articles = self.storage.search_articles(limit=limit or 100)
            
            # 按时间排序
            articles.sort(key=lambda x: x.get('crawl_time', ''), reverse=True)
            
            if limit:
                articles = articles[:limit]
            
            self.logger.info(f"从MinIO存储获取到 {len(articles)} 篇文章")
            return articles
            
        except Exception as e:
            self.logger.error(f"从MinIO存储获取文章失败: {e}")
            return []
    
    def save_results(self, results: Dict, filename: str = None) -> str:
        """保存结果到文件"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'wechat_articles_{timestamp}.json'
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"结果已保存到: {filename}")
        return filename
    
    def get_anti_crawler_stats(self) -> Dict:
        """获取防反爬系统统计信息"""
        if self.use_anti_crawler:
            return self.anti_crawler_session.get_stats()
        else:
            return {"message": "防反爬系统未启用"}
    
    def reset_anti_crawler_stats(self):
        """重置防反爬系统统计信息"""
        if self.use_anti_crawler:
            self.anti_crawler_session.reset_stats()
            self.logger.info("防反爬系统统计信息已重置")

class ScheduledCrawler:
    """定时爬虫类（简化版）"""
    
    def __init__(self, crawler: WeChatCrawler):
        self.crawler = crawler
        self.logger = logging.getLogger(__name__)
        self.is_running = False
    
    def schedule_daily_crawl(self, time_str: str = "08:00"):
        """设置每日早上8点定时爬取（爬取前一天下午3点到今天早上8点的内容）"""
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
                        # 如果有文章，保存到单独的文件
                        filename = f'wechat_{account}_{date_str}.json'
                        # 清理文件名中的特殊字符
                        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                        
                        self.crawler.save_results(results, filename)
                        
                        article_count = len(results['data'])
                        total_articles_saved += article_count
                        
                        self.logger.info(f"公众号 '{account}' 爬取完成: {article_count} 篇文章已保存到 {filename}")
                    else:
                        self.logger.info(f"公众号 '{account}' 在指定时间段内没有发布文章")
                        
                except Exception as e:
                    self.logger.error(f"爬取公众号 '{account}' 时发生错误: {e}")
                    continue
                
                # 添加延时避免请求过快
                time.sleep(random.uniform(3, 8))  # 随机延迟3-8秒
            
            self.logger.info(f"每日定时任务完成: 共处理 {len(accounts)} 个公众号，保存 {total_articles_saved} 篇文章")
        
        # 设置每日定时任务
        schedule.every().day.at(time_str).do(job)
        self.logger.info(f"已设置每日定时任务: 每天{time_str}爬取所有配置的公众号（前一天15:00到当天08:00的内容）")
    
    def run_daily_crawl_now(self):
        """立即执行每日爬取任务（用于测试）"""
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
                    # 如果有文章，保存到单独的文件
                    filename = f'wechat_{account}_{date_str}.json'
                    # 清理文件名中的特殊字符
                    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                    
                    self.crawler.save_results(results, filename)
                    
                    article_count = len(results['data'])
                    total_articles_saved += article_count
                    
                    self.logger.info(f"公众号 '{account}' 爬取完成: {article_count} 篇文章已保存到 {filename}")
                else:
                    self.logger.info(f"公众号 '{account}' 在指定时间段内没有发布文章")
                    
            except Exception as e:
                self.logger.error(f"爬取公众号 '{account}' 时发生错误: {e}")
                continue
            
            # 添加延时避免请求过快
            time.sleep(random.uniform(3, 8))  # 随机延迟3-8秒
        
        self.logger.info(f"手动爬取任务完成: 共处理 {len(accounts)} 个公众号，保存 {total_articles_saved} 篇文章")
        return total_articles_saved
    
    def run_scheduler(self):
        """运行调度器"""
        self.is_running = True
        self.logger.info("定时爬虫调度器启动")
        
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def stop_scheduler(self):
        """停止调度器"""
        self.is_running = False
        self.logger.info("定时爬虫调度器已停止")

def main():
    """主函数：简化版"""
    print("=== 微信公众号爬虫 ===")
    
    # 创建爬虫实例
    crawler = WeChatCrawler()
    
    # 从配置文件加载公众号列表
    accounts = crawler.load_wechat_accounts()
    print(f"\n已加载 {len(accounts)} 个公众号")
    
    # 选择爬取方式
    print("\n选择功能:")
    print("1. 普通爬取（所有配置的公众号）")
    print("2. 测试定时爬取（前一天15:00-今天08:00，按公众号分别保存）")
    print("3. 启动定时任务（每天08:00自动执行）")
    
    choice = input("请输入选择 (1/2/3，默认2): ").strip() or "2"
    
    if choice == "1":
        # 普通爬取所有配置的公众号
        print(f"\n开始爬取所有公众号...")
        results = crawler.crawl_all_configured_accounts(get_real_urls=True, fetch_content=True)
        
        # 保存结果
        filename = crawler.save_results(results)
        print(f"\n爬取完成！")
        print(f"统计: 找到 {results['stats']['total_found']} 篇文章")
        print(f"结果已保存到: {filename}")
        
    elif choice == "2":
        # 测试每日定时爬取
        print("\n开始测试定时爬取...")
        print("时间范围：前一天15:00 到 今天08:00")
        print("文件格式：wechat_公众号名称_2025_0905.json")
        
        scheduled_crawler = ScheduledCrawler(crawler)
        total_saved = scheduled_crawler.run_daily_crawl_now()
        
        print(f"\n测试完成！共保存 {total_saved} 篇文章")
        
    elif choice == "3":
        # 启动定时任务
        print("\n启动定时任务...")
        print("每天早上08:00自动爬取前一天15:00-当天08:00的文章")
        print("按 Ctrl+C 停止")
        
        scheduled_crawler = ScheduledCrawler(crawler)
        scheduled_crawler.schedule_daily_crawl("08:00")
        
        try:
            scheduled_crawler.run_scheduler()
        except KeyboardInterrupt:
            print("\n定时任务已停止")
            scheduled_crawler.stop_scheduler()
            
    else:
        print("无效选择")
        return
    
    print(f"\n📝 提示: 要修改公众号列表，请编辑 {crawler.config_file} 文件")

if __name__ == "__main__":
    main()

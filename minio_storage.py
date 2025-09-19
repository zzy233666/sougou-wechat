#!/usr/bin/env python3
"""
MinIO 对象存储适配器
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import hashlib
from io import BytesIO, StringIO
import os
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class MinIOArticleStorage:
    """MinIO对象存储文章存储器"""
    
    def __init__(self, 
                 endpoint: str = None,
                 access_key: str = None, 
                 secret_key: str = None,
                 bucket_name: str = None,
                 secure: bool = False):
        
        # 从环境变量获取配置
        self.endpoint = endpoint or os.getenv('MINIO_ENDPOINT', 'localhost:9000')
        self.access_key = access_key or os.getenv('MINIO_ACCESS_KEY', '')
        self.secret_key = secret_key or os.getenv('MINIO_SECRET_KEY', '')
        self.bucket_name = bucket_name or os.getenv('MINIO_BUCKET', 'wechat-articles')
        self.secure = secure if secure is not None else os.getenv('MINIO_SECURE', 'false').lower() == 'true'
        
        if not self.access_key or not self.secret_key:
            raise ValueError("MinIO access_key and secret_key must be provided")
        
        # 初始化 MinIO 客户端
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # 初始化存储桶
        self.init_bucket()
        logger.info(f"MinIO存储初始化成功: {self.endpoint}/{self.bucket_name}")
    
    def init_bucket(self):
        """初始化存储桶"""
        try:
            # 检查存储桶是否存在
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"创建存储桶: {self.bucket_name}")
            else:
                logger.info(f"存储桶已存在: {self.bucket_name}")
                
        except S3Error as e:
            logger.error(f"初始化存储桶失败: {e}")
            raise
    
    def _generate_object_key(self, article_data: Dict) -> str:
        """生成对象键名"""
        # 使用标题和时间生成唯一键
        title = article_data.get('title', 'unknown')
        publish_time = article_data.get('publish_time', datetime.now().isoformat())
        
        # 生成hash确保唯一性
        content_hash = hashlib.md5(f"{title}{publish_time}".encode('utf-8')).hexdigest()[:8]
        
        # 按日期分组存储
        date_str = publish_time[:10] if len(publish_time) >= 10 else datetime.now().strftime('%Y-%m-%d')
        
        return f"articles/{date_str}/{content_hash}.json"
    
    def save_article(self, article_data: Dict) -> bool:
        """保存文章到MinIO"""
        try:
            object_key = self._generate_object_key(article_data)
            
            # 检查是否已存在
            if self._article_exists(object_key):
                logger.info(f"文章已存在，跳过保存: {article_data.get('title', '')[:30]}...")
                return False
            
            # 添加保存时间戳
            article_data['saved_at'] = datetime.now().isoformat()
            
            # 转换为JSON字节流
            json_data = json.dumps(article_data, ensure_ascii=False, indent=2)
            json_bytes = BytesIO(json_data.encode('utf-8'))
            
            # 上传到MinIO
            self.client.put_object(
                self.bucket_name,
                object_key,
                json_bytes,
                length=len(json_data.encode('utf-8')),
                content_type='application/json'
            )
            
            logger.info(f"文章保存成功: {object_key}")
            return True
            
        except Exception as e:
            logger.error(f"保存文章失败: {e}")
            return False
    
    def _article_exists(self, object_key: str) -> bool:
        """检查文章是否已存在"""
        try:
            self.client.stat_object(self.bucket_name, object_key)
            return True
        except S3Error:
            return False
    
    def get_articles_by_date(self, 
                            start_date: str = None, 
                            end_date: str = None, 
                            limit: int = None) -> List[Dict]:
        """按日期范围获取文章"""
        try:
            articles = []
            
            # 构建日期前缀
            if start_date and end_date:
                # 遍历日期范围内的所有对象
                date_prefixes = self._generate_date_range(start_date, end_date)
            elif start_date:
                date_prefixes = [f"articles/{start_date}/"]
            else:
                date_prefixes = ["articles/"]
            
            for prefix in date_prefixes:
                objects = self.client.list_objects(
                    self.bucket_name, 
                    prefix=prefix, 
                    recursive=True
                )
                
                for obj in objects:
                    if limit and len(articles) >= limit:
                        break
                        
                    try:
                        # 获取对象数据
                        response = self.client.get_object(self.bucket_name, obj.object_name)
                        article_data = json.loads(response.data.decode('utf-8'))
                        articles.append(article_data)
                        
                    except Exception as e:
                        logger.error(f"读取文章失败 {obj.object_name}: {e}")
                        continue
                
                if limit and len(articles) >= limit:
                    break
            
            # 按时间排序（最新的在前）
            articles.sort(key=lambda x: x.get('publish_time', ''), reverse=True)
            
            return articles[:limit] if limit else articles
            
        except Exception as e:
            logger.error(f"获取文章失败: {e}")
            return []
    
    def _generate_date_range(self, start_date: str, end_date: str) -> List[str]:
        """生成日期范围的前缀列表"""
        from datetime import datetime, timedelta
        
        prefixes = []
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            prefixes.append(f"articles/{current.strftime('%Y-%m-%d')}/")
            current += timedelta(days=1)
        
        return prefixes
    
    def search_articles(self, 
                       query: str = None,
                       source: str = None,
                       start_date: str = None,
                       end_date: str = None,
                       limit: int = 50) -> List[Dict]:
        """搜索文章"""
        # 先获取所有相关文章
        all_articles = self.get_articles_by_date(start_date, end_date)
        
        # 应用过滤条件
        filtered_articles = []
        
        for article in all_articles:
            # 查询条件过滤
            if query:
                title = article.get('title', '').lower()
                summary = article.get('summary', '').lower()
                content = article.get('content', '').lower()
                
                if (query.lower() not in title and 
                    query.lower() not in summary and 
                    query.lower() not in content):
                    continue
            
            # 来源过滤
            if source and source.lower() not in article.get('source', '').lower():
                continue
            
            filtered_articles.append(article)
            
            if len(filtered_articles) >= limit:
                break
        
        return filtered_articles
    
    def get_article_stats(self) -> Dict:
        """获取存储统计信息"""
        try:
            total_count = 0
            total_size = 0
            
            # 统计所有文章
            objects = self.client.list_objects(
                self.bucket_name, 
                prefix="articles/", 
                recursive=True
            )
            
            for obj in objects:
                total_count += 1
                total_size += obj.size
            
            return {
                "total_articles": total_count,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "bucket_name": self.bucket_name,
                "endpoint": self.endpoint
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                "total_articles": 0,
                "total_size_mb": 0,
                "bucket_name": self.bucket_name,
                "endpoint": self.endpoint
            }
    
    def delete_article(self, object_key: str) -> bool:
        """删除文章"""
        try:
            self.client.remove_object(self.bucket_name, object_key)
            logger.info(f"文章删除成功: {object_key}")
            return True
        except Exception as e:
            logger.error(f"删除文章失败: {e}")
            return False
    
    def backup_to_json(self, output_file: str = None) -> str:
        """备份所有文章到JSON文件"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'wechat_articles_backup_{timestamp}.json'
        
        try:
            all_articles = self.get_articles_by_date()
            
            backup_data = {
                "backup_time": datetime.now().isoformat(),
                "total_articles": len(all_articles),
                "articles": all_articles
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"备份完成: {output_file}, 共{len(all_articles)}篇文章")
            return output_file
            
        except Exception as e:
            logger.error(f"备份失败: {e}")
            raise


# 兼容性适配器，保持与原SQLite接口一致
class MinIOArticleStorageAdapter(MinIOArticleStorage):
    """MinIO存储适配器，兼容原有SQLite接口"""
    
    def save_articles(self, articles: List[Dict]) -> int:
        """批量保存文章"""
        saved_count = 0
        for article in articles:
            if self.save_article(article):
                saved_count += 1
        return saved_count
    
    def get_articles_by_query(self, query: str, limit: int = None) -> List[Dict]:
        """根据查询关键字获取文章"""
        return self.search_articles(query=query, limit=limit or 50)
    
    def get_latest_articles(self, limit: int = 10) -> List[Dict]:
        """获取最新文章"""
        return self.get_articles_by_date(limit=limit)
    
    def close(self):
        """关闭连接（MinIO无需显式关闭）"""
        pass


if __name__ == "__main__":
    # 测试代码
    try:
        # 初始化MinIO存储
        storage = MinIOArticleStorage()
        
        # 测试文章数据
        test_article = {
            "title": "测试文章标题",
            "summary": "这是一篇测试文章的摘要",
            "source": "测试来源",
            "publish_time": "2024-01-01 12:00:00",
            "real_url": "https://example.com/test",
            "content": "这是测试文章的完整内容"
        }
        
        # 保存文章
        success = storage.save_article(test_article)
        print(f"保存文章: {'成功' if success else '失败'}")
        
        # 获取统计信息
        stats = storage.get_article_stats()
        print(f"存储统计: {stats}")
        
        # 搜索文章
        results = storage.search_articles(query="测试", limit=5)
        print(f"搜索结果: 找到{len(results)}篇文章")
        
    except Exception as e:
        print(f"测试失败: {e}")

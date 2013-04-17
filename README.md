distribute_crawler
==================

使用scrapy,redis, mongodb,graphite实现的一个分布式网络爬虫,底层存储mongodb集群,分布式使用redis实现,
爬虫状态显示使用graphite实现。

这个工程是我对垂直搜索引擎中分布式网络爬虫的探索实现，它包含一个针对http://www.woaidu.org/ 网站的spider，
将其网站的书名，作者，书籍封面图片，书籍概要，原始网址链接，书籍下载信息和书籍爬取到本地：
* 分布式使用redis实现，redis中存储了工程的request，stats信息，能够对各个机器上的爬虫实现集中管理，这样可以
解决爬虫的性能瓶颈，利用redis的高效和易于扩展能够轻松实现高效率下载

特色：
* 底层存储

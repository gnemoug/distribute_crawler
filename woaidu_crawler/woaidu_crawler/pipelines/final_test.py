#!/usr/bin/python
#-*-coding:utf-8-*-

from pprint import pprint
from woaidu_crawler.utils import color

class FinalTestPipeline(object):
    """
        This only for print the final item for the purpose of debug,because the default
        scrapy output the result,so if you use this pipeline,you better change the scrapy
        source code:
        
        sudo vim /usr/local/lib/python2.7/dist-packages/Scrapy-0.16.4-py2.7.egg/scrapy/core/scrapy.py
        make line 211 like this:
            #log.msg(level=log.DEBUG, spider=spider, **logkws)
    """
    
    def __init__(self):
        self.style = color.color_style()

    @classmethod
    def from_crawler(cls, crawler):
        pipe = cls()
        pipe.crawler = crawler
        return pipe
    
    def process_item(self, item, spider):
        print self.style.NOTICE("SUCCESS(item):" + item['original_url'])
        #pprint(item)
        return item

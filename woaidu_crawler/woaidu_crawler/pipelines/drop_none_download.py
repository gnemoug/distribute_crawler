#!/usr/bin/python
#-*-coding:utf-8-*-

from pprint import pprint
from woaidu_crawler.utils import color
from woaidu_crawler.pipelines.bookfile import NofilesDrop

class DropNoneBookFile(object):
    """
        drop items those book_file and book_file_url are empty. 
    """
    
    Drop_NoneBookFile = True
    
    def __init__(self):
        self.style = color.color_style()

    @classmethod
    def from_crawler(cls, crawler):
        cls.Drop_NoneBookFile = crawler.settings.get('Drop_NoneBookFile',True)
        pipe = cls()
        pipe.crawler = crawler
        return pipe
    
    def process_item(self, item, spider):
        if not item.get('book_file_url',None):
            raise NofilesDrop(item['original_url'])
        
        return item

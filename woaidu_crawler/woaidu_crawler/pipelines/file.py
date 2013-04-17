#!/usr/bin/python
#-*-coding:utf-8-*-

import os
import time
import hashlib
import urlparse
import shutil
import urllib
from urlparse import urlparse
from scrapy import log
from twisted.internet import defer
from pprint import pprint 
from woaidu_crawler.utils import color
from scrapy.utils.misc import md5sum
from collections import defaultdict
from scrapy.utils.misc import arg_to_iter
from scrapy.contrib.pipeline.images import MediaPipeline
from woaidu_crawler.utils.select_result import list_first_item
from scrapy.exceptions import NotConfigured, IgnoreRequest

class FileException(Exception):
    """General file error exception"""
    def __init__(self, file_url=None, *args):
        self.file_url = file_url
        self.style = color.color_style()
        Exception.__init__(self, *args)

    def __str__(self):#####for usage: print e
        print self.style.ERROR("ERROR(FileException): %s"%(Exception.__str__(self),))
        
        return Exception.__str__(self)

class FSFilesStore(object):

    def __init__(self, basedir):
        if '://' in basedir:
            basedir = basedir.split('://', 1)[1]
        self.basedir = basedir
        self._mkdir(self.basedir)
        self.created_directories = defaultdict(set)

    def persist_file(self, key, file_content, info, filename):
        self._mkdir(os.path.join(self.basedir, *key.split('/')), info)
        absolute_path = self._get_filesystem_path(key,filename)
        with open(absolute_path,"w") as wf:
            wf.write(file_content)

        with open(absolute_path, 'rb') as file_content:
            checksum = md5sum(file_content)
            
        return checksum

    def stat_file(self, key, info):
        """
            the stat is the file key dir,
            the last_modified is the file that saved to the file key dir.
        """
        
        keydir = os.path.join(self.basedir, *key.split('/'))
        filenames = os.listdir(keydir)
        if len(filenames) != 1:
            shutil.rmtree(keydir,True)
            return {}
        else:
            filename = list_first_item(filenames)
        
        absolute_path = self._get_filesystem_path(key)
        try:
            last_modified = os.path.getmtime(absolute_path)
        except:  # FIXME: catching everything!
            return {}

        with open(os.path.join(absolute_path,filename), 'rb') as file_content:
            checksum = md5sum(file_content)

        return {'last_modified': last_modified, 'checksum': checksum}

    def _get_filesystem_path(self, key,filename=None):
        path_comps = key.split('/')
        if filename:
            path_comps.append(filename)
            return os.path.join(self.basedir, *path_comps)
        else:
            return os.path.join(self.basedir, *path_comps)

    def _mkdir(self, dirname, domain=None):
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        
        #XXX:str.rfind(sub[, start[, end]])
        #Return the highest index in the string where substring sub is found,
        #such that sub is contained within s[start:end]. 
        dirname = dirname[:dirname.rfind('/')] if domain else dirname
        seen = self.created_directories[domain] if domain else set()
        if dirname not in seen:
            seen.add(dirname)

class FilePipeline(MediaPipeline):
    """
        download file pipeline.
    """
    
    MEDIA_NAME = 'file'
    EXPIRES = 90
    URL_GBK_DOMAIN = []
    ATTACHMENT_FILENAME_UTF8_DOMAIN = []
    STORE_SCHEMES = {
        '': FSFilesStore,
        'file': FSFilesStore,
    }
    
    FILE_EXTENTION = ['.doc','.txt','.docx','.rar','.zip','.pdf']
    
    def __init__(self,store_uri,download_func=None):
        if not store_uri:
            raise NotConfigured
        self.store = self._get_store(store_uri)
        self.style = color.color_style()
        super(FilePipeline, self).__init__(download_func=download_func)

    @classmethod
    def from_settings(cls, settings):
        cls.EXPIRES = settings.getint('FILE_EXPIRES', 90)
        cls.ATTACHMENT_FILENAME_UTF8_DOMAIN = settings.get('ATTACHMENT_FILENAME_UTF8_DOMAIN',[])
        cls.URL_GBK_DOMAIN = settings.get('URL_GBK_DOMAIN',[])
        cls.FILE_EXTENTION = settings.get('FILE_EXTENTION',[])
        store_uri = settings['FILE_STORE']
        return cls(store_uri)

    def _get_store(self, uri):
        if os.path.isabs(uri):  # to support win32 paths like: C:\\some\dir
            scheme = 'file'
        else:
            scheme = urlparse.urlparse(uri).scheme

        store_cls = self.STORE_SCHEMES[scheme]
        return store_cls(uri)

    def media_downloaded(self, response, request, info):
        """
            Handler for success downloads.
        """
        
        referer = request.headers.get('Referer')

        if response.status != 200:
            log.msg(format='%(medianame)s (code: %(status)s): Error downloading %(medianame)s from %(request)s referred in <%(referer)s>',
                    level=log.WARNING, spider=info.spider,medianame=self.MEDIA_NAME,
                    status=response.status, request=request, referer=referer)
            raise FileException(request.url,'%s: download-error'%(request.url,))

        if not response.body:
            log.msg(format='%(medianame)s (empty-content): Empty %(medianame)s from %(request)s referred in <%(referer)s>: no-content',
                    level=log.WARNING, spider=info.spider,medianame=self.MEDIA_NAME,
                    request=request, referer=referer)
            raise FileException(request.url,'%s: empty-content'%(request.url,))

        status = 'cached' if 'cached' in response.flags else 'downloaded'
        log.msg(format='%(medianame)s (%(status)s): Downloaded %(medianame)s from %(request)s referred in <%(referer)s>',
                level=log.DEBUG, spider=info.spider,medianame=self.MEDIA_NAME,
                status=status, request=request, referer=referer)

        if self.is_valid_content_type(response):
            raise FileException(request.url,'%s: invalid-content_type'%(request.url,))
        
        filename = self.get_file_name(request,response)
        
        if not filename:
            raise FileException(request.url,'%s: noaccess-filename'%(request.url,))
        
        self.inc_stats(info.spider, status)
        
        try:
            key = self.file_key(request.url)#return the SHA1 hash of the file url
            checksum = self.store.persist_file(key,response.body,info,filename)
        except FileException as exc:
            whyfmt = '%(medianame)s (error): Error processing %(medianame)s from %(request)s referred in <%(referer)s>: %(errormsg)s'
            log.msg(format=whyfmt, level=log.WARNING, spider=info.spider,medianame=self.MEDIA_NAME,
                    request=request, referer=referer, errormsg=str(exc))
            raise
        
        return {'url': request.url, 'path': key, 'checksum': checksum}

    def media_failed(self, failure, request, info):
        if not isinstance(failure.value, IgnoreRequest):
            referer = request.headers.get('Referer')
            log.msg(format='%(medianame)s (unknown-error): Error downloading '
                           '%(medianame)s from %(request)s referred in '
                           '<%(referer)s>: %(exception)s',
                    level=log.WARNING, spider=info.spider, exception=failure.value,
                    medianame=self.MEDIA_NAME, request=request, referer=referer)
        
        raise FileException(request.url,'%s: Error downloading'%(request.url,))

    def media_to_download(self, request, info):
        def _onsuccess(result):
            
            if not result:
                return  # returning None force download

            last_modified = result.get('last_modified', None)
            if not last_modified:
                return  # returning None force download

            age_seconds = time.time() - last_modified
            age_days = age_seconds / 60 / 60 / 24
            if age_days > self.EXPIRES:
                return  # returning None force download

            referer = request.headers.get('Referer')
            log.msg(format='%(medianame)s (uptodate): Downloaded %(medianame)s from %(request)s referred in <%(referer)s>',
                    level=log.DEBUG, spider=info.spider,
                    medianame=self.MEDIA_NAME, request=request, referer=referer)
            self.inc_stats(info.spider, 'uptodate')

            checksum = result.get('checksum', None)
            
            return {'url': request.url, 'path': key, 'checksum': checksum}

        key = self.file_key(request.url)#return the SHA1 hash of the file url
        dfd = defer.maybeDeferred(self.store.stat_file, key, info)
        dfd.addCallbacks(_onsuccess, lambda _: None)
        dfd.addErrback(log.err, self.__class__.__name__ + '.store.stat_file')
        return dfd

    def is_valid_content_type(self,response):
        """
            judge whether is it a valid response by the Content-Type.
        """
        return True

    def inc_stats(self, spider, status):
        spider.crawler.stats.inc_value('%s_file_count'%(self.MEDIA_NAME,) , spider=spider)
        spider.crawler.stats.inc_value('%s_file_status_count/%s' % (self.MEDIA_NAME,status), spider=spider)

    def file_key(self, url):
        """
            return the SHA1 hash of the file url
        """
        
        file_guid = hashlib.sha1(url).hexdigest()
        return '%s/%s' % (urlparse(url).netloc,file_guid)

    def get_file_name(self,request,response):
        """
            Get the raw file name that the sever transfer to.
            
            It examine two places:Content-Disposition,url.
        """
        
        content_dispo = response.headers.get('Content-Disposition','')
        filename = ""
        #print response.headers
        if content_dispo:
            for i in content_dispo.split(';'):
                if "filename" in i:
                    #XXX:use filename= for the specific case that = in the filename
                    filename = i.split('filename=')[1].strip(" \n\'\"")
                    break
        
        if filename:
            #XXX:it the result is:
            #MPLS TE Switching%E6%96%B9%E6%A1%88%E7%99%BD%E7%9A%AE%E4%B9%A6.pdf
            #use urllib.unquote(filename) instead
            if urlparse(request.url).netloc in self.ATTACHMENT_FILENAME_UTF8_DOMAIN:
                filename = filename.decode("utf-8")
            else:
                filename = filename.decode("gbk")
            #print "Content-Disposition:","*"*30,filename
        else:
            guessname = request.url.split('/')[-1]
            #os.path.splitext:
            #Split the pathname path into a pair (root, ext) such that root + ext == path
            if os.path.splitext(guessname)[1].lower() in self.FILE_EXTENTION:
                if urlparse(request.url).netloc in self.URL_GBK_DOMAIN:
                    filename = urllib.unquote(guessname).decode("gbk").encode("utf-8")
                else:
                    filename = urllib.unquote(guessname)
                #print "url:","*"*30,filename
        
        return filename

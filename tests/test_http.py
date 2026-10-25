import json
from pathlib import Path
import sys
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Handler

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def post(self,path,payload):
        req=urllib.request.Request(self.url+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req) as response:return json.load(response)
    def test_assets_and_operators(self):
        for route in ('/','/app.js','/style.css'):
            with urllib.request.urlopen(self.url+route) as response:self.assertEqual(response.status,200)
        with urllib.request.urlopen(self.url+'/api/operators') as response:self.assertEqual(len(json.load(response)),11)
    def test_both_modes(self):
        r=self.post('/api/optimize',{'mode':'python','source':'def f(a):\n    return a + 0','budget':20})
        self.assertIn('return a',r['optimized_python']);self.assertTrue(r['validation']['valid'])
        r=self.post('/api/optimize',{'mode':'tac','source':'total = a * 1','outputs':'total','budget':20})
        self.assertEqual(r['example']['selected'],{'total':3})
    def test_invalid_program_and_cross_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.post('/api/optimize',{'mode':'python','source':'import os'})
        self.assertEqual(ctx.exception.code,400)
        req=urllib.request.Request(self.url+'/api/optimize',data=b'{}',headers={'Origin':'https://example.invalid'})
        with self.assertRaises(urllib.error.HTTPError) as ctx:urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code,403)
    def test_benchmark_rejects_bad_size(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.post('/api/benchmark',{'programs':1})
        self.assertEqual(ctx.exception.code,400)

if __name__=='__main__':unittest.main()

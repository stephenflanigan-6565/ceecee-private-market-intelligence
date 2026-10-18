import unittest
from flask import Flask
from pmi_public_info import bp

class PublicInfoTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__)
        self.app.register_blueprint(bp)
        self.client=self.app.test_client()
    def test_public_readonly_routes(self):
        for route in ("/about","/privacy"):
            with self.subTest(route=route):
                r=self.client.get(route)
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.mimetype,"text/html")
                self.assertNotIn("Set-Cookie",r.headers)
                self.assertEqual(self.client.post(route).status_code,405)
                self.assertEqual(self.client.head(route).data,b"")
    def test_scope_contact_and_retention(self):
        home=self.client.get("/about").get_data(as_text=True)
        privacy=self.client.get("/privacy").get_data(as_text=True)
        self.assertIn('href="/privacy"',home)
        for text in ("drive.file","DigitalOcean","revok","does not delete","4xpipaddict@gmail.com","original","owner-only"):
            self.assertIn(text,privacy)
    def test_no_dynamic_research_or_active_content(self):
        for route in ("/about","/privacy"):
            a=self.client.get(route)
            b=self.client.get(route+"?access_key=DO_NOT_EXPOSE&property=PRIVATE")
            self.assertEqual(a.data,b.data)
            self.assertNotIn(b"DO_NOT_EXPOSE",b.data)
            self.assertNotIn(b"<script",b.data)
            self.assertNotIn(b"<form",b.data)
            self.assertIn("default-src 'none'",b.headers["Content-Security-Policy"])
    def test_only_new_routes(self):
        self.assertEqual({r.rule for r in self.app.url_map.iter_rules() if r.endpoint!="static"},{"/about","/privacy"})

if __name__=="__main__": unittest.main()

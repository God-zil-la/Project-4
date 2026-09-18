from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class PublicSEOTests(SimpleTestCase):
    def test_sitemap_is_valid_xml_with_only_public_canonical_urls(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml; charset=utf-8')
        root = ElementTree.fromstring(response.content)
        ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
        self.assertEqual(root.tag, ns + 'urlset')
        urls = [node.text for node in root.findall(f'{ns}url/{ns}loc')]
        self.assertEqual(urls, [
            'https://www.myaiassistantapp.se/',
            'https://www.myaiassistantapp.se/privacy/',
            'https://www.myaiassistantapp.se/delete-account/',
        ])
        for url in urls:
            with self.subTest(url=url):
                page = self.client.get(urlsplit(url).path)
                self.assertEqual(page.status_code, 200)
                self.assertNotIn('noindex', page.content.decode().lower())
                self.assertNotIn('noindex', page.get('X-Robots-Tag', '').lower())

    @override_settings(ALLOWED_HOSTS=['alternate.example'])
    def test_sitemap_does_not_use_request_host(self):
        response = self.client.get('/sitemap.xml', HTTP_HOST='alternate.example')
        self.assertContains(response, 'https://www.myaiassistantapp.se/')
        self.assertNotContains(response, 'alternate.example')

    def test_robots_allows_public_pages_and_assets_and_blocks_private_areas(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        rules = RobotFileParser()
        rules.parse(response.content.decode().splitlines())
        self.assertEqual(rules.site_maps(), ['https://www.myaiassistantapp.se/sitemap.xml'])
        for agent in ['Googlebot', 'Bingbot', 'OtherBot']:
            for path in ['/', '/privacy/', '/delete-account/', '/sitemap.xml', '/static/css/style.css']:
                with self.subTest(agent=agent, allowed=path):
                    self.assertTrue(rules.can_fetch(agent, path))
            for path in [
                '/accounts/delete/', '/accounts/login/', '/accounts/api/me/',
                '/admin/', '/dashboard/', '/payments/', '/media/private.pdf',
                '/bots/', '/bots/1/playground/', '/bots/analytics/',
                '/bots/api/dashboard/', '/bots/api/analytics/',
                '/bots/api/bots/1/knowledge/', '/bots/api/conversations/',
            ]:
                with self.subTest(agent=agent, blocked=path):
                    self.assertFalse(rules.can_fetch(agent, path))

    def test_footer_links_to_public_deletion_page_and_onward_to_confirmation(self):
        self.assertEqual(reverse('delete_account'), '/delete-account/')
        self.assertEqual(reverse('accounts:delete_account'), '/accounts/delete/')
        self.assertContains(self.client.get('/'), 'href="/delete-account/"')
        self.assertContains(self.client.get('/delete-account/'), 'href="/accounts/delete/"')
        self.assertRedirects(
            self.client.get('/accounts/delete/'),
            '/accounts/login/?next=/accounts/delete/',
            fetch_redirect_response=False,
        )

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True)
    def test_endpoints_work_over_production_https(self):
        for path in ['/sitemap.xml', '/robots.txt']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, secure=True).status_code, 200)
                self.assertEqual(self.client.get(path).status_code, 301)

    def test_head_and_unsupported_methods(self):
        for path in ['/sitemap.xml', '/robots.txt']:
            with self.subTest(path=path):
                response = self.client.head(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b'')
                self.assertEqual(self.client.post(path).status_code, 405)

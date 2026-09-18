from django.test import SimpleTestCase, override_settings


@override_settings(SECURE_SSL_REDIRECT=False)
class CanonicalURLTests(SimpleTestCase):
    @override_settings(
        ALLOWED_HOSTS=["myaiassistantapp.se", "www.myaiassistantapp.se"],
    )
    def test_apex_redirect_preserves_path_and_query(self):
        response = self.client.get(
            "/privacy/?test=1",
            HTTP_HOST="myaiassistantapp.se",
            secure=True,
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "https://www.myaiassistantapp.se/privacy/?test=1",
        )

    @override_settings(
        ALLOWED_HOSTS=["www.myaiassistantapp.se"],
    )
    def test_www_host_is_not_redirected(self):
        response = self.client.get(
            "/privacy/",
            HTTP_HOST="www.myaiassistantapp.se",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))

    @override_settings(
        ALLOWED_HOSTS=["www.myaiassistantapp.se"],
    )
    def test_public_pages_have_www_canonical_urls(self):
        expected = {
            "/": "https://www.myaiassistantapp.se/",
            "/privacy/": "https://www.myaiassistantapp.se/privacy/",
            "/delete-account/": "https://www.myaiassistantapp.se/delete-account/",
        }

        for path, canonical_url in expected.items():
            with self.subTest(path=path):
                response = self.client.get(
                    path,
                    HTTP_HOST="www.myaiassistantapp.se",
                    secure=True,
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    f'<link rel="canonical" href="{canonical_url}">',
                    html=True,
                )
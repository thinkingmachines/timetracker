from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse

import click
import requests


class RequestHandler(BaseHTTPRequestHandler):
    client_id = None
    client_secret = None

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        params = dict(parse_qsl(urlparse(self.path).query))
        if "code" not in params:
            self.wfile.write(b"Missing code")
            return
        resp = requests.get(
            "https://slack.com/api/oauth.v2.access",
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": params["code"],
                "redirect_uri": "http://localhost:8000",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            self.wfile.write(data["error"].encode())
            return
        access_token = data.get("authed_user", {}).get("access_token")
        if not access_token:
            self.wfile.write(b"Failed to retrieve access token")
            return
        self.wfile.write(access_token.encode())


@click.command()
@click.option("--client-id", type=str)
@click.option("--client-secret", type=str)
def main(client_id, client_secret):
    print(
        "Open https://slack.com/oauth/v2/authorize?client_id=55260380816.156708423974&user_scope=chat:write&redirect_uri=http://localhost:8000"
    )
    RequestHandler.client_id = client_id
    RequestHandler.client_secret = client_secret
    httpd = HTTPServer(("", 8000), RequestHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    main(auto_envvar_prefix="SLACK")

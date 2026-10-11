"""
Fetch a rostests folder from the artifact server (host_server.py) on the build machine.

Usage: fetch_tests.py [--server URL] [--timeout SECONDS] FOLDER_NAME LOCAL_DEST

FOLDER_NAME is the name of the folder on the server (the basename of
"${ROSTESTS_PREFIX}-${SUFFIX}"), which identifies the commit/run to test.
The folder is only downloaded once the build machine has created the
"FOLDER_NAME.ready" marker next to it, signalling that it is complete.
"""
import argparse
import os
import shutil
import sys
import time
import urllib
import urllib2
from HTMLParser import HTMLParser

DEFAULT_SERVER_URL = "http://192.168.37.16:8000"
DEFAULT_TIMEOUT = 4 * 60 * 60  # Seconds to wait for the folder to become ready, 0 = forever
POLL_INTERVAL = 5  # Seconds to wait before checking again
READY_SUFFIX = ".ready"
NOTIFY_ATTEMPTS = 5


class SimpleDirectoryParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr, value in attrs:
                if attr == "href":
                    self.links.append(value)


def make_url(server_url, name):
    return server_url.rstrip("/") + "/" + urllib.quote(name)


def is_ready(server_url, folder_name):
    try:
        urllib2.urlopen(make_url(server_url, folder_name + READY_SUFFIX), timeout=10)
        return True
    except Exception:
        # Server isn't up yet or the folder isn't complete yet
        return False


def download_file(remote_url, local_path):
    response = urllib2.urlopen(remote_url, timeout=60)
    with open(local_path, "wb") as f:
        shutil.copyfileobj(response, f)


def download_folder(remote_url, local_dir):
    # remote_url must end with a slash, so the relative links of the listing can be appended to it
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)

    parser = SimpleDirectoryParser()
    parser.feed(urllib2.urlopen(remote_url, timeout=60).read().decode("utf-8"))

    for link in parser.links:
        if link in ["../", "./", "/"] or link.startswith("?"):
            continue

        name = urllib.unquote(link.rstrip("/"))
        if link.endswith("/"):
            download_folder(remote_url + link, os.path.join(local_dir, name))
        else:
            download_file(remote_url + link, os.path.join(local_dir, name))


def notify_download_complete(server_url, folder_name):
    done_url = server_url.rstrip("/") + "/download-complete"

    for attempt in range(NOTIFY_ATTEMPTS):
        try:
            req = urllib2.Request(done_url, data=folder_name.encode("utf-8"))
            response = urllib2.urlopen(req, timeout=10)
            if response.getcode() == 200:
                print "[CLIENT] Win7 server notified and unblocked."
                return True
        except Exception as e:
            print "[CLIENT] Failed to notify Win7 server: " + str(e)
        time.sleep(POLL_INTERVAL)

    return False


def fetch(server_url, folder_name, local_dest, timeout):
    print "[CLIENT] Waiting for " + folder_name + " on " + server_url + "..."

    deadline = time.time() + timeout if timeout > 0 else None
    while not is_ready(server_url, folder_name):
        if deadline is not None and time.time() > deadline:
            print "[CLIENT] Timed out waiting for " + folder_name + " to become ready."
            return False
        time.sleep(POLL_INTERVAL)

    print "[CLIENT] Found test folder: " + folder_name
    print "[CLIENT] Downloading to " + local_dest + "..."

    # Download into a temporary folder, so an aborted download never looks like a complete one
    partial_dest = local_dest + ".partial"
    for path in [partial_dest, local_dest]:
        if os.path.exists(path):
            shutil.rmtree(path)

    download_folder(make_url(server_url, folder_name) + "/", partial_dest)
    os.rename(partial_dest, local_dest)
    print "[CLIENT] Download complete."

    # Notify Win7 to delete the source folder and exit host_server.py
    if not notify_download_complete(server_url, folder_name):
        print "[CLIENT] Warning: Win7 server was not notified, its copy of " + folder_name + " is left behind."

    return True


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Fetch a rostests folder from the artifact server.")
    arg_parser.add_argument("--server", default=DEFAULT_SERVER_URL, help="URL of host_server.py")
    arg_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Seconds to wait for the folder, 0 = forever")
    arg_parser.add_argument("folder_name", help="Name of the folder on the server")
    arg_parser.add_argument("local_dest", help="Local path to download the folder to")
    args = arg_parser.parse_args()

    if not fetch(args.server, args.folder_name, args.local_dest, args.timeout):
        sys.exit(1)

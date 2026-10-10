import os
import time
import urllib
import urllib2
from HTMLParser import HTMLParser

SERVER_URL = "http://192.168.37.16:8000"
LOCAL_TESTS_DIR = r"C:\tests"
POLL_INTERVAL = 5  # Seconds to wait before checking again


class SimpleDirectoryParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr, value in attrs:
                if attr == "href":
                    self.links.append(value)


def download_folder(remote_folder_name, relative_path=""):
    remote_url = (
        SERVER_URL
        + "/"
        + relative_path
        + urllib.quote(remote_folder_name)
        + "/"
    )
    local_target = os.path.join(
        LOCAL_TESTS_DIR, relative_path.replace("/", os.sep)
    )

    if not os.path.exists(local_target):
        os.makedirs(local_target)

    req = urllib2.urlopen(remote_url)
    parser = SimpleDirectoryParser()
    parser.feed(req.read().decode("utf-8"))

    for link in parser.links:
        if link in ["../", "./", "/"]:
            continue

        decoded = urllib.unquote(link)
        if link.endswith("/"):
            download_folder(
                decoded.rstrip("/"),
                relative_path + urllib.quote(remote_folder_name) + "/",
            )
        else:
            file_url = remote_url + urllib.quote(decoded)
            urllib.urlretrieve(
                file_url, os.path.join(local_target, decoded)
            )


def notify_download_complete(folder_name):
    done_url = SERVER_URL + "/download-complete"
    req = urllib2.Request(done_url, data=folder_name.encode("utf-8"))
    try:
        response = urllib2.urlopen(req)
        if response.getcode() == 200:
            print "[CLIENT] Win7 server notified and unblocked."
    except Exception as e:
        print "[CLIENT] Failed to notify Win7 server: " + str(e)


def wait_and_fetch():
    print "[CLIENT] Waiting for Win7 test server to become available..."

    while True:
        try:
            req = urllib2.urlopen(SERVER_URL, timeout=3)
            html_content = req.read().decode("utf-8")

            parser = SimpleDirectoryParser()
            parser.feed(html_content)

            folders = [
                urllib.unquote(l.rstrip("/"))
                for l in parser.links
                if l.endswith("/") and l not in ["../", "./", "/"]
            ]

            if folders:
                target_folder = folders[0]
                print "[CLIENT] Found test folder: " + target_folder
                print "[CLIENT] Downloading..."

                download_folder(target_folder)
                print "[CLIENT] Download complete."

                # Notify Win7 to delete the source folder and exit server.py
                notify_download_complete(target_folder)
                return True

        except Exception:
            # Server isn't up yet or no folders are present; retry silently
            pass

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    wait_and_fetch()

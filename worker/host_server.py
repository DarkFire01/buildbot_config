import http.server
import os
import shutil
import socketserver
import urllib.parse

ARTIFACTS_DIR = r"C:\Tests_For_Carrier-Win2003-x64"
PORT = 8000

class ArtifactHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ARTIFACTS_DIR, **kwargs)

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)

        if parsed_path.path == "/download-complete":
            content_length = int(self.headers.get("Content-Length", 0))
            folder_name = self.rfile.read(content_length).decode("utf-8").strip()

            safe_folder_name = os.path.basename(folder_name)
            target_path = os.path.join(ARTIFACTS_DIR, safe_folder_name)

            # Cleanup source artifacts on Win7 host
            if os.path.exists(target_path) and os.path.isdir(target_path):
                try:
                    shutil.rmtree(target_path)
                    print(
                        f"[SERVER] Cleaned up served folder: {safe_folder_name}"
                    )
                except Exception as e:
                    print(
                        f"[SERVER] Error deleting {safe_folder_name}: {str(e)}"
                    )

            # Respond to Vista before exiting
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"Download confirmed. Releasing Win7 Buildbot step."
            )

            # Stop server loop
            self.server.should_exit = True
        else:
            self.send_error(404, "Unknown endpoint")


class StoppableTCPServer(socketserver.TCPServer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_exit = False

    def serve_until_done(self):
        while not self.should_exit:
            self.handle_request()


def run_server():
    os.chdir(ARTIFACTS_DIR)
    socketserver.TCPServer.allow_reuse_address = True
    server = StoppableTCPServer(("", PORT), ArtifactHandler)
    print(
        f"[SERVER] Serving {ARTIFACTS_DIR} on port {PORT}. Waiting for download..."
    )
    server.serve_until_done()
    print("[SERVER] Download complete! Releasing Win7 pipeline.")


if __name__ == "__main__":
    run_server()

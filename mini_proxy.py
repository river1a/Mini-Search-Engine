import socket, socketserver, select, re

class ProxyHandler(socketserver.StreamRequestHandler):
    timeout = 10
    def _relay(self, client, upstream):
        sockets = [client, upstream]
        while True:
            r, _, _ = select.select(sockets, [], [], self.timeout)
            if not r: return
            if client in r:
                data = client.recv(65536)
                if not data: return
                upstream.sendall(data)
            if upstream in r:
                data = upstream.recv(65536)
                if not data: return
                client.sendall(data)

    def handle(self):
        self.connection.settimeout(self.timeout)
        data = self.rfile.readline()
        if not data: return
        first_line = data.decode("iso-8859-1").strip()
        if not first_line: return
        parts = first_line.split(" ", 2)
        if len(parts) < 2: return
        method, target = parts[0], parts[1]
        headers = {}
        while True:
            line = self.rfile.readline()
            if not line: return
            line = line.decode("iso-8859-1")
            if line in ("\r\n", "\n"): break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        if method.upper() == "CONNECT":
            host, port = target.split(":")
            port = int(port)
            upstream = socket.create_connection((host, port), timeout=self.timeout)
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            self._relay(self.connection, upstream)
            upstream.close()
            return
        m = re.match(r"(?i)http://([^/]+)(/.*)?", target)
        if m:
            hostport = m.group(1)
            path = m.group(2) or "/"
        else:
            hostport = headers.get("host")
            path = target if target.startswith("/") else "/"
        if not hostport: return
        if ":" in hostport:
            host, port = hostport.split(":", 1)
            port = int(port)
        else:
            host, port = hostport, 80
        upstream = socket.create_connection((host, port), timeout=self.timeout)
        req = f"{method} {path} HTTP/1.1\r\n"
        if "host" not in headers:
            headers["host"] = hostport
        headers.pop("proxy-connection", None)
        headers["connection"] = "close"
        upstream.sendall(req.encode("iso-8859-1"))
        for k, v in headers.items():
            upstream.sendall(f"{k.title()}: {v}\r\n".encode("iso-8859-1"))
        upstream.sendall(b"\r\n")
        self._relay(self.connection, upstream)
        upstream.close()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

def serve(port=8081):
    with ThreadedTCPServer(("127.0.0.1", port), ProxyHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    import sys
    port = 8081
    if len(sys.argv) > 1:
        try: port = int(sys.argv[1])
        except: pass
    print(f"mini proxy listening on 127.0.0.1:{port}")
    serve(port)

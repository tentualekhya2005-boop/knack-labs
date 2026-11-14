import sys
import fakeredis

def main():
    print("Starting local Redis emulator on 127.0.0.1:6379...", flush=True)
    server = fakeredis.TcpFakeServer(("127.0.0.1", 6379))
    print("Redis emulator listening on 127.0.0.1:6379", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Redis emulator...", flush=True)
        server.shutdown()

if __name__ == "__main__":
    main()


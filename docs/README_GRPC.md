# Describes gRPC generation and local client checks for the active Decider service.
# RAKSHAK gRPC

The authoritative contract is `backend/api/gRPC/protos/decision.proto`. Generated code is written
under `build/proto/` and must never be edited manually.

Generate Python bindings:

```powershell
.\.venv\Scripts\python.exe scripts\dev\gen_decider_proto.py
```

Generate Python and C++ bindings:

```powershell
.\.venv\Scripts\python.exe scripts\dev\gen_decider_proto.py --cpp
```

The C++ command requires `protoc` and `grpc_cpp_plugin` on `PATH`.

Start the server:

```powershell
.\.venv\Scripts\rakshak-grpc.exe
```

Run the bundled clients:

```powershell
.\.venv\Scripts\python.exe -m backend.api.gRPC.clients.cli_decide --kind log --text "test log"
.\.venv\Scripts\python.exe -m backend.api.gRPC.clients.stream_logs --file .\sample.log
.\.venv\Scripts\python.exe -m backend.api.gRPC.clients.upload_and_decide --file .\sample.bin
```

All RPCs require `x-api-key` metadata unless `RAKSHAK_REQUIRE_API_KEY=0`. See [API.md](API.md)
for stream rules, limits, TLS variables, and the C++ integration contract.

# Generates Python and optional C++ code from the decider protobuf contract.
import argparse, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROTO_DIR = ROOT / "backend" / "api" / "gRPC" / "protos"
PROTO = PROTO_DIR / "decision.proto"
PY_OUT = ROOT / "build" / "proto" / "py"
CPP_OUT = ROOT / "build" / "proto" / "cpp"
def run(cmd: list[str]) -> None:
    print("+", " ".join(map(str, cmd)))
    subprocess.check_call(cmd)


def generate_python() -> None:
    PY_OUT.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={PY_OUT}", f"--grpc_python_out={PY_OUT}",
        str(PROTO),
    ])


def generate_cpp() -> None:
    protoc = shutil.which("protoc")
    grpc_plugin = shutil.which("grpc_cpp_plugin")
    if not protoc or not grpc_plugin:
        raise SystemExit(
            "C++ generation requires `protoc` and `grpc_cpp_plugin` on PATH."
        )

    CPP_OUT.mkdir(parents=True, exist_ok=True)
    run([
        protoc, f"-I{PROTO_DIR}",
        f"--cpp_out={CPP_OUT}", f"--grpc_out={CPP_OUT}",
        f"--plugin=protoc-gen-grpc={grpc_plugin}", str(PROTO),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate decider protobuf bindings.")
    parser.add_argument(
        "--cpp",
        action="store_true",
        help="also generate C++ bindings; requires protoc and grpc_cpp_plugin",
    )
    args = parser.parse_args()

    generate_python()
    if args.cpp:
        generate_cpp()


if __name__ == "__main__":
    main()

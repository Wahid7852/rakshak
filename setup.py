# Generates packaged Python protobuf bindings while building RAKSHAK distributions.
import subprocess, sys
from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent
PROTO_DIR = ROOT / "backend" / "api" / "gRPC" / "protos"
PROTO = PROTO_DIR / "decision.proto"
GENERATED_DIR = ROOT / "backend" / "api" / "gRPC" / "generated"


class BuildPyWithProto(build_py):
    def run(self) -> None:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.check_call([
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={GENERATED_DIR}",
            f"--grpc_python_out={GENERATED_DIR}",
            str(PROTO),
        ])
        super().run()


setup(cmdclass={"build_py": BuildPyWithProto})

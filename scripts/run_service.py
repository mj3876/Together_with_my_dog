import argparse
import os
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="대전 반려견 여행 서비스를 로컬에서 실행합니다.")
    parser.add_argument("--demo", action="store_true", help="키 없이 가상 장소·가상 이동시간으로 체험")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.demo:
        os.environ["APP_MODE"] = "demo"
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

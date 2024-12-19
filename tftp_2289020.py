#!/usr/bin/python3
import socket
import argparse
from struct import pack

DEFAULT_PORT = 69  # 기본 포트 번호는 69번
BLOCK_SIZE = 512  # 데이터 블록 크기
DEFAULT_TRANSFER_MODE = 'octet'  # 전송 모드: 'octet' (바이너리 전송)
TIMEOUT = 5  # 서버 응답 대기 시간

# TFTP 명령의 OpCode 정의
OPCODE = {'RRQ': 1, 'WRQ': 2, 'DATA': 3, 'ACK': 4, 'ERROR': 5}

# TFTP 에러 코드 및 메시지 정의
ERROR_CODE = {
    0: "Not defined, see error message (if any).",
    1: "File not found.",
    2: "Access violation.",
    3: "Disk full or allocation exceeded.",
    4: "Illegal TFTP operation.",
    5: "Unknown transfer ID.",
    6: "File already exists.",
    7: "No such user."
}

def send_wrq(filename, mode, sock, server_address):
    """
    WRQ(쓰기 요청) 메시지를 서버로 전송합니다.
    """
    format = f'>h{len(filename)}sB{len(mode)}sB'
    wrq_message = pack(format, OPCODE['WRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(wrq_message, server_address)

def send_rrq(filename, mode, sock, server_address):
    """
    RRQ(읽기 요청) 메시지를 서버로 전송합니다.
    """
    format = f'>h{len(filename)}sB{len(mode)}sB'
    rrq_message = pack(format, OPCODE['RRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(rrq_message, server_address)

def tftp_put(filename, sock, server_address):
    """
    파일 업로드(put) 기능
    - 69번 포트 또는 지정된 포트로 WRQ 요청 전송
    - 서버로부터 ACK 응답을 수신 후 데이터 블록 전송
    - 전송 모드는 'octet' 모드만 지원
    """
    sock.settimeout(TIMEOUT)  # 서버 응답 대기 시간 설정
    send_wrq(filename, DEFAULT_TRANSFER_MODE, sock, server_address)  # WRQ 전송 (octet 모드)

    try:
        ack, address = sock.recvfrom(4)  # 서버로부터 ACK 응답 대기
    except socket.timeout:
        print("타임아웃: 서버로부터 WRQ에 대한 응답이 없습니다. 종료합니다.")  # 서버 응답 없음 처리
        return

    with open(filename, 'rb') as file:
        block_number = 1
        while True:
            file_block = file.read(BLOCK_SIZE)  # 파일 데이터 블록 읽기
            if not file_block:
                break

            # 데이터 패킷 생성 및 전송
            data_packet = pack(f'>hh{len(file_block)}s', OPCODE['DATA'], block_number, file_block)
            sock.sendto(data_packet, address)

            try:
                ack, address = sock.recvfrom(4)  # 서버로부터 ACK 응답 대기
                ack_opcode = int.from_bytes(ack[:2], 'big')
                ack_block_number = int.from_bytes(ack[2:], 'big')

                if ack_opcode == OPCODE['ACK'] and ack_block_number == block_number:
                    block_number += 1
            except socket.timeout:
                print("타임아웃: 파일 업로드 중 서버로부터 응답이 없습니다. 다시 시도합니다...")  # 서버 응답 없음 처리
                continue

def tftp_get(filename, sock, server_address):
    """
    파일 다운로드(get) 기능
    - 69번 포트 또는 지정된 포트로 RRQ 요청 전송
    - 서버로부터 DATA 패킷 수신 및 ACK 응답 전송
    - 전송 모드는 'octet' 모드만 지원
    """
    sock.settimeout(TIMEOUT)  # 서버 응답 대기 시간 설정
    send_rrq(filename, DEFAULT_TRANSFER_MODE, sock, server_address)  # RRQ 전송 (octet 모드)

    try:
        data, address = sock.recvfrom(516)  # 서버로부터 DATA 패킷 대기
    except socket.timeout:
        print("타임아웃: 서버로부터 RRQ에 대한 응답이 없습니다. 종료합니다.")  # 서버 응답 없음 처리
        return

    with open(filename, 'wb') as file:
        block_number = 1
        while True:
            opcode = int.from_bytes(data[:2], 'big')
            if opcode == OPCODE['DATA']:
                block = int.from_bytes(data[2:4], 'big')
                if block == block_number:
                    file.write(data[4:])  # 수신한 데이터 저장
                    send_ack(block, sock, address)  # ACK 응답 전송
                    block_number += 1

                if len(data[4:]) < BLOCK_SIZE:  # 마지막 블록 확인
                    break
            elif opcode == OPCODE['ERROR']:
                error_code = int.from_bytes(data[2:4], 'big')
                print(f"Error: {ERROR_CODE.get(error_code, 'Unknown error')}")  # 에러 메시지 처리
                break
            else:
                break

            try:
                data, address = sock.recvfrom(516)  # 다음 DATA 패킷 대기
            except socket.timeout:
                print("타임아웃: 파일 다운로드 중 서버로부터 응답이 없습니다. 종료합니다.")  # 서버 응답 없음 처리
                break

def send_ack(block_number, sock, address):
    """
    ACK 응답 패킷 전송
    """
    ack_packet = pack(f'>hh', OPCODE['ACK'], block_number)
    sock.sendto(ack_packet, address)

# 명령줄 인자 파서 설정
parser = argparse.ArgumentParser(description="TFTP client program")
parser.add_argument("host", help="Server IP address", type=str)  # 서버 IP 주소
parser.add_argument("operation", help="get or put command", type=str)  # 작업 종류 (get 또는 put)
parser.add_argument("filename", help="File name to transfer", type=str)  # 전송할 파일 이름
parser.add_argument("-p", "--port", help="Server port number", type=int, default=DEFAULT_PORT)  # 서버 포트 번호 설정
args = parser.parse_args()

server_ip = args.host
server_port = args.port  # 사용자 지정 포트 설정
server_address = (server_ip, server_port)

# UDP 소켓 생성
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

if args.operation.lower() == "get":
    tftp_get(args.filename, sock, server_address)  # 파일 다운로드
elif args.operation.lower() == "put":
    tftp_put(args.filename, sock, server_address)  # 파일 업로드
else:
    print("Invalid command. Use 'get' or 'put'.")  # 유효하지 않은 명령 처리

sock.close()
